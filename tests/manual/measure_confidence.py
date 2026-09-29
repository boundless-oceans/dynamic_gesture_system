"""手工测量：模型置信度 + 画面运动量，在某个场景下的分布

    python tests/manual/measure_confidence.py --label 走路 --seconds 45

需要摄像头和显示器（有预览窗口，你能看到自己在画面里的位置）。

**它解决什么问题**

发现"人在镜头前走过（不做手势）也被识别成左/右抛出，置信度到 0.7~0.99"，
而 `CONFIDENCE_THRESHOLD = 0.6` —— **会真的触发翻页**。

实测三个场景后确认：**光调门槛救不了** —— 走路的峰值 0.988 和真手势的 1.000
几乎贴在一起，任何阈值都要在"漏掉真手势"和"放进走路"之间二选一。

所以这里**同时量第二个指标：运动面积占比**。判据是：

    做手势 → 只有手那一小块在动（几个百分点）
    走路   → 整个人/大半个画面在动（几十个百分点）

也就是"局部运动 vs 全局运动"。如果这两个分布分得开，就能用它做一层过滤，
而不必引入手掌检测（那要新依赖）。

**为什么单独一个脚本，而不是改 smoke_inference**

smoke 是通用调试工具（逐条滚动打印）。这个是**一次性测量**，要的是
"最后出分布"，而且要能装进测试库里横向对比。
"""

import argparse
import os
import sys
import time
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from src.core.frame_buffer import FrameBuffer
from src.core.gesture_mapper import label_cn
from src.core.inference import GestureRecognizer, InferenceThread
from src.ui.camera_widget import CameraWidget
from src import config

BUCKET = 0.05
THRESHOLDS = [0.60, 0.70, 0.80, 0.90]      # 0.6 是当前触发门槛

# 运动判据：像素通道差超过它才算"这块变了"
PIXEL_DIFF = 25
MOTION_MARKS = [0.05, 0.10, 0.20, 0.35, 0.50]   # 报告这些占比之上的样本比例


def motion_ratio(window) -> float:
    """窗口内"明显变化"的像素占比（0~1）。

    用**窗口首帧与尾帧**做差分：两帧相隔约 0.56s，正好是模型看的时间跨度，
    所以量的是"这段时间里画面移动了多少"。
    """
    if len(window) < 2:
        return 0.0
    a = window[0].astype(np.int16)
    b = window[-1].astype(np.int16)
    diff = np.abs(b - a).max(axis=2)            # 每像素取三通道里的最大差
    return float((diff > PIXEL_DIFF).mean())


def _hist(values, n) -> None:
    print("  分布（每格 %.2f）:" % BUCKET)
    for lo_i in range(int(1 / BUCKET)):
        lo = round(lo_i * BUCKET, 2)
        hi = round(lo + BUCKET, 2)
        cnt = sum(1 for v in values if lo <= v < hi)
        if cnt:
            bar = "#" * max(1, round(cnt / n * 60))
            print("  %.2f-%.2f  %-60s %d" % (lo, hi, bar, cnt))


class MeasureWindow(QMainWindow):

    def __init__(self, label: str, seconds: float):
        super().__init__()
        self.label = label
        self.seconds = seconds
        self.raws = []
        self.motions = []
        self.labels = Counter()
        self._last_report = 0.0

        self.setWindowTitle("测量：%s" % label)
        self.resize(640, 560)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.frame_buffer = FrameBuffer()
        self.camera = CameraWidget()
        layout.addWidget(self.camera)

        self.recognizer = GestureRecognizer()
        if self.recognizer.status != "ok":
            print("[测量] 权重异常：%s %s"
                  % (self.recognizer.status, self.recognizer.status_detail))
        self.inference_thread = InferenceThread(self.frame_buffer, self.recognizer)
        self.inference_thread.result_ready.connect(self._on_result)
        self.inference_thread.start()
        self.camera.start(self.frame_buffer)

        print("[测量] 「%s」开始，%g 秒。现在开始做你要测的动作…" % (label, seconds))
        QTimer.singleShot(int(seconds * 1000), self.close)

    def _on_result(self, result):
        self.raws.append(float(result.get("raw_confidence", 0.0)))
        self.labels[label_cn(int(result.get("raw_gesture", result["gesture"])))] += 1
        # 再取一次缓冲：拿到的和模型刚看的几乎是同一批帧（前后差一帧以内）
        self.motions.append(motion_ratio(
            self.frame_buffer.get_latest(config.SAMPLE_WINDOW_FRAMES)))

        now = time.time()
        if now - self._last_report >= 3.0:        # 每 3 秒报一次，确认还在跑
            self._last_report = now
            print("[测量] 已采 %d 条，最近 raw=%.3f 运动面积=%.1f%% %s"
                  % (len(self.raws), self.raws[-1], self.motions[-1] * 100,
                     label_cn(int(result.get("raw_gesture", result["gesture"])))))

    def closeEvent(self, event):
        self.inference_thread.stop()
        self.camera.stop()
        self._report()
        event.accept()

    def _report(self):
        n = len(self.raws)
        if not n:
            print("\n[测量] 一条样本都没采到 —— 摄像头没出帧？")
            return
        s = sorted(self.raws)
        m = sorted(self.motions)
        pct = lambda arr, q: arr[min(len(arr) - 1, int(q * len(arr)))]   # noqa: E731

        print("\n" + "=" * 66)
        print("场景「%s」  实际采样 %.1f 秒 / %d 条" % (self.label, self.seconds, n))
        print("=" * 66)

        print("\n【模型 raw 置信度】")
        print("  min=%.3f  P50=%.3f  P90=%.3f  P99=%.3f  max=%.3f"
              % (s[0], pct(s, .50), pct(s, .90), pct(s, .99), s[-1]))
        _hist(self.raws, n)
        print("  超过门槛的比例:")
        for t in THRESHOLDS:
            hit = sum(1 for v in self.raws if v >= t)
            tag = "   ← 当前触发门槛" if abs(t - config.CONFIDENCE_THRESHOLD) < 1e-9 else ""
            print("    >= %.2f   %5.1f%%  (%d/%d)%s" % (t, hit / n * 100, hit, n, tag))

        print("\n【运动面积占比】← 判断「局部运动 vs 全局运动」能不能分开")
        print("  min=%.1f%%  P50=%.1f%%  P90=%.1f%%  max=%.1f%%"
              % (m[0] * 100, pct(m, .50) * 100, pct(m, .90) * 100, m[-1] * 100))
        print("  超过各档占比的样本比例:")
        for t in MOTION_MARKS:
            hit = sum(1 for v in self.motions if v >= t)
            print("    >= %4.1f%%    %5.1f%%  (%d/%d)"
                  % (t * 100, hit / n * 100, hit, n))

        print("\ntop1 标签分布:")
        for name, cnt in self.labels.most_common():
            print("  %-10s %5.1f%%  (%d)" % (name, cnt / n * 100, cnt))
        print()

        # 一行式汇总，方便多次运行横向对比（grep 这一行）
        print("@@summary\t%s\traw_P50=%.3f\traw_P90=%.3f\traw_max=%.3f\t"
              "motion_P50=%.3f\tmotion_P90=%.3f\tmotion_max=%.3f"
              % (self.label, pct(s, .50), pct(s, .90), s[-1],
                 pct(m, .50), pct(m, .90), m[-1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="未命名", help="这次测的是哪个场景")
    ap.add_argument("--seconds", type=float, default=45.0)
    args = ap.parse_args()

    app = QApplication(sys.argv)
    win = MeasureWindow(args.label, args.seconds)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
