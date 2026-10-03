"""手工测量：HaGRID 静态手势模型（34 类 ResNet18）在我们这套摄像头下到底能不能用

    python tests/manual/measure_static_gesture.py --label OK --mode zone --seconds 30
    python tests/manual/measure_static_gesture.py --label 不做手势 --mode zone --seconds 30

需要摄像头和显示器（CameraWidget 自带预览，你能看到自己在画面里的位置）。

**它回答什么问题**

评审要求"加 OK / 点赞这类静态手势"。素材项目的权重是个 **34 类 ResNet18 分类器**，
其中第 33 类是 **no_gesture** —— 这正是治"走路被认成抛出"要的那个信号：
模型能直接说"这只手没在做手势"，比"有没有检测到手"更准。

但那个分类器是吃**裁好的手**的：它的参考实现 `demo.py` 用 MediaPipe 先检测手、
裁出来再分类。而我们**不想为它引入 mediapipe** —— 素材项目的 requirements 里
`mediapipe==0.10.21` 要求 `protobuf<5`，而我们 `gesture` 环境是 protobuf 7.x，
装它要降级 protobuf（动共享环境）。

**所以这个脚本要回答的是：不裁手行不行？**

    --mode full   整帧直接喂
    --mode zone   只喂"中央交互区"（与动态模型看到的同一块画面，见 model_view_rect）

判据：

  * 做 ok / 点赞时，top1 是否稳定命中对应类
  * **不做手势、手放在画面里时，top1 是否稳定是 `no_gesture`** ← 这条最难也最关键
  * 中途走开/走过时，会不会冒出高分手势类

zone 或 full 能分清 → **零新依赖**，直接进方案；
分不清 → 才需要回来讨论要不要为 mediapipe 降 protobuf。

**预处理**严格照抄素材项目 `configs/ResNet18.yaml` 的 `test_transforms`
（LongestMaxSize(224) → PadIfNeeded(224, 灰 144) → Normalize）。
⚠ 注意它的 mean/std 与动态模型那组（ImageNet）**不同**，两者不能混用。

**权重从哪来**：素材项目里的 `downloads/ResNet18.pth`（约 89MB）。
用 `--weights` 指过去即可；想固定下来的话，把它拷进仓库的 `weights/` 再用默认值。
"""

import argparse
import os
import sys
import time
from collections import Counter

import cv2
import numpy as np
import torch
from torchvision.models import resnet18
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.frame_buffer import FrameBuffer
from src.core.inference import model_view_rect
from src.ui.camera_widget import CameraWidget

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_WEIGHTS = os.path.join(REPO, "weights", "hagrid_resnet18.pth")

# 34 类，顺序即模型输出下标（素材项目 constants.py 的 targets）
LABELS = [
    "grabbing", "grip", "holy", "point", "call", "three3", "timeout", "xsign",
    "hand_heart", "hand_heart2", "little_finger", "middle_finger", "take_picture",
    "dislike", "fist", "four", "like", "mute", "ok", "one", "palm", "peace",
    "peace_inverted", "rock", "stop", "stop_inverted", "three", "three2", "two_up",
    "two_up_inverted", "three_gun", "thumb_index", "thumb_index2", "no_gesture",
]
NUM_CLASSES = len(LABELS)
NO_GESTURE = LABELS.index("no_gesture")

# 只是为了让终端好读，不参与任何判断
CN = {
    "ok": "OK", "like": "点赞", "palm": "张开手掌", "stop": "停止",
    "fist": "握拳", "dislike": "踩", "peace": "剪刀手", "point": "单指",
    "no_gesture": "无手势", "mute": "嘘", "rock": "摇滚",
}

IMG_SIZE = 224
MEAN = np.array([0.54, 0.499, 0.474], dtype=np.float32)
STD = np.array([0.234, 0.235, 0.231], dtype=np.float32)
PAD_VALUE = 144          # PadIfNeeded 的填充值（灰）


def cn(name: str) -> str:
    return CN.get(name, name)


def preprocess(img: np.ndarray) -> torch.Tensor:
    """照抄 HaGRID 的 test_transforms：LongestMaxSize → PadIfNeeded → Normalize

    输入是**已经转好的 RGB**（帧缓冲里存的就是 RGB，见 camera.py）。
    albumentations 的 Normalize(max_pixel_value=255) 等价于 (x/255 - mean) / std。
    """
    h, w = img.shape[:2]
    scale = IMG_SIZE / float(max(h, w))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((IMG_SIZE, IMG_SIZE, 3), PAD_VALUE, dtype=np.uint8)
    top, left = (IMG_SIZE - nh) // 2, (IMG_SIZE - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    x = canvas.astype(np.float32) / 255.0
    x = (x - MEAN) / STD
    return torch.from_numpy(x.transpose(2, 0, 1))[None]


def load_model(path: str):
    if not os.path.isfile(path):
        sys.exit("[测量] 找不到权重：%s\n"
                 "用 --weights 指到素材项目的 downloads/ResNet18.pth" % path)
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
