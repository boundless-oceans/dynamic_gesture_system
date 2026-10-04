"""HaGRID 静态手势模型（34 类 ResNet18）—— 架构 A：只做加法

和动态模型（DSTE-Net，认"手**刚才做了什么动作**"）不同，这个模型认的是
**手此刻的形状**。两者回答的不是同一个问题，所以**不能拿置信度比大小**：
13 类 softmax 与 34 类 softmax 不是一个尺度，而且两边都没做校准
（动态模型在"走路不做手势"时都能给到 0.99）。

**架构 A 的含义 —— 本模块只做加法：**

    * 判成 ``ok`` / ``like`` → 交给 main_window 触发动作（见 gesture_mapper.STATIC_TO_CONTROL）
    * 判成其余 32 类（含 ``no_gesture``）→ **弃权**，动态模型照旧

所以这个模型判错绝大多数类时**产生不了任何后果**。它**没有否决权** ——
不含"判成 no_gesture 就把动态结果丢掉"那一层（那是架构 B，见 WORKLOG 第九节第 5 条）。

**权重从哪来**：素材盘上的 `downloads/ResNet18.pth`（89MB，34 类），
拷成 `weights/hagrid_resnet18.pth` 即可。类别顺序取自同目录 `configs/ResNet18.yaml`
的 `targets`，已与 `fc.weight` 的 `[34, 512]` 形状核对过。

⚠ `weights/` 已 gitignore —— **交付时要把它一起带走**，否则这两个手势静默失效
（加载失败只打一行日志、状态置成 missing，不会崩）。

**预处理**严格照抄那份 yaml 的 `test_transforms`：
LongestMaxSize(224) → PadIfNeeded(224, 灰 144) → Normalize。
⚠ 它的 mean/std 与动态模型那组（ImageNet）**不同**，两者不能混用。
"""
import os

import cv2
import numpy as np
import torch
import torchvision.models as tvm

from src import config
from src.core.gesture_mapper import STATIC_TO_CONTROL

# 34 个类，顺序即模型输出下标（configs/ResNet18.yaml 的 targets）。
# ⚠ **改这个列表等于让所有输出错位**，而且界面看着仍"正常工作"，所以有用例钉死它。
LABELS = [
    "grabbing", "grip", "holy", "point", "call", "three3", "timeout", "xsign",
    "hand_heart", "hand_heart2", "little_finger", "middle_finger", "take_picture",
    "dislike", "fist", "four", "like", "mute", "ok", "one", "palm", "peace",
    "peace_inverted", "rock", "stop", "stop_inverted", "three", "three2", "two_up",
    "two_up_inverted", "three_gun", "thumb_index", "thumb_index2", "no_gesture",
]
NUM_CLASSES = len(LABELS)
NO_GESTURE = LABELS.index("no_gesture")

IMG_SIZE = 224
MEAN = np.array([0.54, 0.499, 0.474], dtype=np.float32)
STD = np.array([0.234, 0.235, 0.231], dtype=np.float32)
PAD_VALUE = 144          # PadIfNeeded 的填充值（灰）


def preprocess(img: np.ndarray) -> torch.Tensor:
    """那份 yaml 里的 test_transforms，输入 RGB 的 numpy 图，输出 (1, 3, 224, 224)。

    albumentations 的 `Normalize(max_pixel_value=255)` 等价于 (x/255 - mean) / std。

    刻意**不引入 albumentations**：它做的两件事就是"长边缩到 224"和"居中补灰边"，
    用 cv2 手写完全等价（有用例拿合成图把几何结果钉住），而为了 20 行预处理
    多装一个包不划算。
    """
    h, w = img.shape[:2]
    longest = max(h, w)
    scale = IMG_SIZE / float(longest) if longest else 1.0
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    # 缩小用 INTER_AREA（先平均再抽样，等价于 albumentations 默认走的那条）；
    # 放大用 INTER_LINEAR。素材项目是放大缩小共用一种插值，这里分得更细一点。
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    resized = cv2.resize(img, (nw, nh), interpolation=interp)
    canvas = np.full((IMG_SIZE, IMG_SIZE, 3), PAD_VALUE, dtype=np.uint8)
    top, left = (IMG_SIZE - nh) // 2, (IMG_SIZE - nw) // 2
    canvas[top:top + nh, left:left + nw] = resized
    x = canvas.astype(np.float32) / 255.0
    x = (x - MEAN) / STD
    return torch.from_numpy(np.ascontiguousarray(x.transpose(2, 0, 1)))[None]


def action_for(label: str, confidence: float) -> str | None:
    """这一帧该触发哪个动作；不该触发则返回 None。

    做成**纯函数**：不用起模型、不用摄像头，就能断言"哪些类会说话、哪些弃权"
    以及门槛边界 —— 那是本模块最要紧的一条策略（见文件头）。

    ⚠ 门槛**故意比动态那边严**（0.75 vs 0.6）。理由不是"34 类更可靠"，而是
    **两者的观测机会数量差一个量级**：
      * 动态手势一次只有一发，错过就没了 → 门槛要放低
      * 静态姿势被持续观测（推理每 0.6 秒一次，举一秒就是十几次机会）→
        错过一帧的成本是零，完全可以把门槛抬高
    再加上后果不对称：静态误触发会把访客从正在看的页面**弹走**。
    """
    if label is None or confidence is None:
        return None
    if confidence < config.STATIC_CONFIDENCE_THRESHOLD:
        return None
    return STATIC_TO_CONTROL.get(label)


class StaticGestureRecognizer:
    """34 类 ResNet18。**只加不减**：认不出 ok/点赞 就什么都不做。"""

    def __init__(self):
        # 刻意钉在 CPU：resnet18 单次约 10ms（动态模型是 583ms），
        # 搬到 GPU 光是主机↔显存的往返就比算本身贵。
        self.model = None
        # ok / missing / error —— 与 GestureRecognizer 同一套语义。
        # 非 ok 时 predict() 恒返回 None（弃权），不会静默地用随机权重输出
        # "看着挺像"的结果。
        self.status = "ok"
        self.status_detail = ""
        self._load()

    def _load(self):
        path = config.STATIC_WEIGHTS_PATH
        if not os.path.exists(path):
            self.status = "missing"
            self.status_detail = path
            print(f"[Static] 未找到静态手势权重，OK/点赞手势不启用: {path}", flush=True)
            return
        try:
            model = tvm.resnet18(num_classes=NUM_CLASSES)
            sd = torch.load(path, map_location="cpu", weights_only=False)
            # 权重文件外面套了一层 {"MODEL_STATE": ...}（同目录还有 OPTIMIZER_STATE 等）
            state = sd["MODEL_STATE"] if isinstance(sd, dict) and "MODEL_STATE" in sd else sd
            model.load_state_dict(state, strict=True)   # 结构不对就直接报错，不静默降级
            model.eval()
            self.model = model
            print(f"[Static] 静态手势模型已加载（{NUM_CLASSES} 类）: {path}", flush=True)
        except Exception as e:
            self.status = "error"
            self.status_detail = str(e)
            print(f"[Static] 静态手势权重加载失败，OK/点赞手势不启用: {e}", flush=True)

    def predict(self, frame: np.ndarray) -> dict | None:
        """对**一帧**做分类。frame 是已经裁好的 RGB 图（裁哪一块由调用方决定，
        见 inference.static_input_frame）。

        返回 ``{"label", "index", "confidence", "top3"}``；模型不可用时返回 None。
        """
        if self.model is None or frame is None or frame.size == 0:
            return None
        with torch.inference_mode():
            probs = torch.softmax(self.model(preprocess(frame))[0], dim=0)
            top = torch.topk(probs, k=3)
        idx = top.indices.tolist()
        conf = top.values.tolist()
        return {
            "label": LABELS[idx[0]],
            "index": idx[0],
            "confidence": round(conf[0], 4),
            "top3": [(LABELS[i], round(c, 4)) for i, c in zip(idx, conf)],
        }
