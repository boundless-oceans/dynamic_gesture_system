"""手工测量：HaGRID 静态手势模型（34 类 ResNet18）在我们这套摄像头下到底能不能用

    python tests/manual/measure_static_gesture.py --label OK --mode zone --seconds 30
    python tests/manual/measure_static_gesture.py --label 不做手势 --mode zone --seconds 30

需要摄像头和显示器（CameraWidget 自带预览，你能看到自己在画面里的位置）。

**它回答什么问题**

评审要求"加 OK / 点赞这类静态手势"。素材项目的权重是个 **34 类 ResNet18 分类器**，
其中第 33 类是 **no_gesture**。

但那个分类器是吃**裁好的手**的：它的参考实现 `demo.py` 用 MediaPipe 先检测手、
裁出来再分类。而我们**不想为它引入 mediapipe** —— 素材项目的 requirements 里
`mediapipe==0.10.21` 要求 `protobuf<5`，而我们 `gesture` 环境是 protobuf 7.x，
装它要降级 protobuf（动共享环境）。

**所以这个脚本要回答的是：不裁手行不行？**

    --mode full   整帧直接喂
    --mode zone   只喂"中央交互区"（与动态模型看到的同一块画面，见 model_view_rect）

⚠ 这个脚本**用的就是生产代码的那一份**（`static_gesture.LABELS` / `.preprocess`），
  不是另抄一份 —— 否则测出来的不是真管线，测了也白测。

要跑的四个场景（前两个决定架构 A 能不能上，后两个决定架构 B）：

  | --label      | 关心的 |
  |---|---|
  | `OK`         | top1 是否稳定命中 `ok`（架构 A 的绑定之一）|
  | `点赞`       | top1 是否稳定命中 `like`（架构 A 的绑定之二）|
  | `不做手势`   | top1 是否稳定是 `no_gesture` ← **最难也最关键** |
  | `做动态手势` | 做向左/向右抛、单击时，静态模型输出什么 ← **决定架构 B 可不可行** |

判据：前两个 + 第三个都能分清 → **零新依赖**，架构 A 直接上；
分不清 → 才需要回来讨论要不要为 mediapipe 降 protobuf。

**权重**：默认取仓库里的 `weights/hagrid_resnet18.pth`（素材盘的 ResNet18.pth 拷过来），
`--weights` 可以指别处。
"""

import argparse
import os
import sys
import time
from collections import Counter

import torch
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.frame_buffer import FrameBuffer
from src.core.inference import model_view_rect
from src.core.static_gesture import LABELS, NUM_CLASSES, NO_GESTURE, preprocess
from src.ui.camera_widget import CameraWidget

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_WEIGHTS = os.path.join(REPO, "weights", "hagrid_resnet18.pth")

# 只是为了让终端好读，不参与任何判断
CN = {
    "ok": "OK", "like": "点赞", "palm": "张开手掌", "stop": "停止",
    "fist": "握拳", "dislike": "踩", "peace": "剪刀手", "point": "单指",
    "no_gesture": "无手势", "mute": "嘘", "rock": "摇滚",
}


def cn(name: str) -> str:
    return CN.get(name, name)


def load_model(path: str):
    if not os.path.isfile(path):
        sys.exit("[测量] 找不到权重：%s\n"
                 "把素材盘的 downloads/ResNet18.pth 拷成这个路径，或用 --weights 指过去" % path)
    from torchvision.models import resnet18
    sd = torch.load(path, map_location="cpu", weights_only=False)
    state = sd["MODEL_STATE"] if isinstance(sd, dict) and "MODEL_STATE" in sd else sd
    model = resnet18(num_classes=NUM_CLASSES)
    model.load_state_dict(state, strict=True)      # 结构不对就直接报错，不静默降级
    model.eval()
    print("[测量] 权重已载入：%s" % path)
    return model


class MeasureWindow(QMainWindow):

    def __init__(self, model, label: str, mode: str, seconds: float, interval_ms: int):
        super().__init__()
        self.model = model
        self.label = label
        self.mode = mode
        self.seconds = seconds

        self.tops = []            # 每次采样的 (top1 名, 置信度)
        self.ng_hits = 0          # no_gesture 排在 top1 的次数
        self._last_report = 0.0

        self.setWindowTitle("静态手势测量：%s（%s）" % (label, mode))
        self.resize(640, 520)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.frame_buffer = FrameBuffer()
        self.camera = CameraWidget()
        layout.addWidget(self.camera)
        self.camera.start(self.frame_buffer)

        print("[测量] 「%s」开始（mode=%s），%g 秒。现在开始做这个动作…"
              % (label, mode, seconds))
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(interval_ms)
        QTimer.singleShot(int(seconds * 1000), self.close)

    # ---- 每 tick 跑一次静态模型 ----
    def _tick(self):
        frames = self.frame_buffer.get_latest(1)
        if not frames:
            return
        frame = frames[-1]
        if self.mode == "zone":
            x, y, w, h = model_view_rect(frame.shape[1], frame.shape[0])
            frame = frame[int(y):int(y + h), int(x):int(x + w)]
            if frame.size == 0:
                return

        with torch.no_grad():
            logits = self.model(preprocess(frame))[0]
            probs = torch.softmax(logits, dim=0)
            top = torch.topk(probs, k=3)

        names = [LABELS[i] for i in top.indices.tolist()]
        confs = top.values.tolist()
        self.tops.append((names[0], confs[0]))
        if names[0] == "no_gesture":
            self.ng_hits += 1

        now = time.time()
        if now - self._last_report >= 3.0:
            self._last_report = now
            n = len(self.tops)
            print("[测量] %d 条  top3: %s"
                  % (n, "  ".join("%s %.2f" % (cn(a), b)
                                  for a, b in zip(names, confs))))

    def closeEvent(self, event):
        self.timer.stop()
        self.camera.stop()
        self._report()
        event.accept()

    def _report(self):
        n = len(self.tops)
        if not n:
            print("\n[测量] 一条样本都没采到 —— 摄像头没出帧？")
            return
        confs = sorted(c for _, c in self.tops)

        def pct(arr, q):
            return arr[min(len(arr) - 1, int(q * len(arr)))]

        print("\n" + "=" * 66)
        print("场景「%s」  mode=%s  实测 %.1f 秒 / %d 条"
              % (self.label, self.mode, self.seconds, n))
        print("=" * 66)

        print("\n【top1 标签分布】")
        for name, cnt in Counter(t for t, _ in self.tops).most_common():
            print("  %-16s %5.1f%%  (%d)" % (cn(name), cnt / n * 100, cnt))

        print("\n【top1 置信度】")
        print("  min=%.3f  P50=%.3f  P90=%.3f  max=%.3f"
              % (confs[0], pct(confs, .50), pct(confs, .90), confs[-1]))

        ng = self.ng_hits / n * 100
        print("\n【no_gesture 命中】top1 是 no_gesture 占 %.1f%%" % ng)

        print()
        print("@@summary\t%s\tmode=%s\tN=%d\tno_gesture=%.3f\t"
              "top1_P50=%.3f\ttop1_max=%.3f"
              % (self.label, self.mode, n, ng, pct(confs, .50), confs[-1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="未命名", help="这次做的是哪个动作")
    ap.add_argument("--mode", choices=("full", "zone"), default="zone",
                    help="full=整帧，zone=只喂中央交互区")
    ap.add_argument("--seconds", type=float, default=30.0)
    ap.add_argument("--weights", default=DEFAULT_WEIGHTS)
    ap.add_argument("--interval-ms", type=int, default=150, help="多久跑一次静态模型")
    args = ap.parse_args()

    model = load_model(args.weights)
    app = QApplication(sys.argv)
    win = MeasureWindow(model, args.label, args.mode, args.seconds, args.interval_ms)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
