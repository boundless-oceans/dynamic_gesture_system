"""全局配置"""

import os

# ---- 项目路径 ----
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 模型 ----
# 权重文件路径（IPN Hand 预训练模型）
MODEL_WEIGHTS_PATH = os.path.join(ROOT_DIR, "weights", "TSQ_ipnhand_RGB_resnet50_shift0.50_blockres_avg_segment8_e50.pth")
# 类别数（IPN Hand: 13）
NUM_CLASSES = 13
# Backbone
ARCH = "resnet50"

# ---- 推理参数 ----
# 每次推理的帧数 = 模型 n_segment，由 checkpoint 固定（fc1 维度=8），不能改。
NUM_SEGMENTS = 8
# 从最近 ~0.5s 的缓冲里均匀抽 8 帧（铺开时间跨度，动态手势更完整、结果更稳）
SAMPLE_WINDOW_FRAMES = 15     # ~0.5s @30fps（需 <= FRAME_BUFFER_MAX）
INFERENCE_INTERVAL_MS = 20    # 循环额外间隔（毫秒）。推理本身已是瓶颈，这里只防忙等
# 概率平滑：最近 SMOOTH_FRAMES 次的 softmax 取平均，抑制单次误判抖动
SMOOTH_FRAMES = 3
# 动作触发门槛：低于则不累加去抖/触发操作
CONFIDENCE_THRESHOLD = 0.6
# 显示门槛：悬浮窗显示识别名所需的最低置信度（更低显示"无手势"）
DISPLAY_CONFIDENCE = 0.35
# 显示保持：高置信手势消失后，仍保留显示这么久（毫秒），避免瞬时动态手势一闪就没
DISPLAY_HOLD_MS = 800

# ---- 图像预处理 ----
INPUT_SIZE = 224              # 送入网络尺寸
SCALE_SIZE = 256              # 短边缩放
INPUT_MEAN = [0.485, 0.456, 0.406]
INPUT_STD = [0.229, 0.224, 0.225]

# ---- 摄像头 ----
CAMERA_INDEX = 0              # 0=默认摄像头
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30               # 采集帧率
# 预览画面是否做 CLAHE 增强（仅显示用）。
# 注意：喂给模型的帧始终是干净 RGB（与训练一致），不做增强。
CAMERA_ENHANCE_PREVIEW = True
# 喂给模型的帧是否先做水平镜像。
# IPN-Hand 训练数据以右利手为主；若右手准、左手不准，
# 可改成 False（喂不镜像帧）再对比左右手表现。
CAMERA_MIRROR_FEED = True

# ---- 帧缓冲 ----
FRAME_BUFFER_MAX = 32         # 缓冲最多存多少帧

# ---- 去抖 ----
CONSISTENCY_COUNT = 3         # 连续 N 次相同结果才输出

# ---- 手势标签（IPN-Hand 13 类，对应 assets/gestures.json）----
# 完整标签码见 gesture_mapper.py 的 IPN_HAND_LABELS
GESTURE_LABELS: dict = {}
