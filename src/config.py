"""全局配置"""

import json
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

# ---- 推理后端 ----
# 实测：本模型(含动态分组卷积) ONNX Runtime CPU 比 PyTorch 更慢(0.72x)，故默认关闭。
# 保留开关与导出脚本，便于将来在其它 CPU/OpenVINO 上复用。
USE_ONNX = False
ONNX_MODEL_PATH = os.path.join(ROOT_DIR, "weights", "gesture.onnx")

# ---- 推理参数 ----
# 每次推理的帧数 = 模型 n_segment，由 checkpoint 固定（fc1 维度=8），不能改。
NUM_SEGMENTS = 8
# 从最近 ~0.5s 的缓冲里均匀抽 8 帧（铺开时间跨度，动态手势更完整、结果更稳）
SAMPLE_WINDOW_FRAMES = 15     # ~0.5s @30fps（需 <= FRAME_BUFFER_MAX）
INFERENCE_INTERVAL_MS = 20    # 循环额外间隔（毫秒）。推理本身已是瓶颈，这里只防忙等
# 概率平滑：最近 SMOOTH_FRAMES 次的 softmax 取平均，抑制单次误判抖动
SMOOTH_FRAMES = 2
# 动作触发门槛：低于则不累加去抖/触发操作
CONFIDENCE_THRESHOLD = 0.6
# 显示门槛：悬浮窗显示识别名所需的最低置信度（更低显示"无手势"）
DISPLAY_CONFIDENCE = 0.35
# 显示保持：高置信手势消失后，仍保留显示这么久（毫秒），避免瞬时动态手势一闪就没
DISPLAY_HOLD_MS = 1000
# 显示切换门槛：想"抢走"当前显示改成另一个手势，新结果置信度需达到这个值；
# 否则保持当前显示（避免动作结束后被一个中等置信的错误类抢走）
DISPLAY_SWITCH_CONFIDENCE = 0.6

# ---- 图像预处理 ----
INPUT_SIZE = 224              # 送入网络尺寸
SCALE_SIZE = 256              # 短边缩放
INPUT_MEAN = [0.485, 0.456, 0.406]
INPUT_STD = [0.229, 0.224, 0.225]

# ---- 摄像头 ----
CAMERA_INDEX = 0              # 手动指定时的摄像头索引（CAMERA_AUTO_SELECT=False 时生效）
# 自动选择摄像头：优先外接（通常索引 1+），没有外接时用自带（索引 0）
CAMERA_AUTO_SELECT = True
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
# 预览画面上是否画出"手势交互区"提示框。
# 模型只处理画面中央一块（见 inference.model_view_rect），四周根本看不到。
# 把这个范围画出来，访客就知道该站哪里、手该伸到哪儿，也顺带减少
# "画面里好几个人各做各的"带来的混乱。嫌乱可以关掉。
CAMERA_SHOW_ZONE = True

# ---- 帧缓冲 ----
FRAME_BUFFER_MAX = 32         # 缓冲最多存多少帧

# ---- 去抖 ----
CONSISTENCY_COUNT = 2         # 连续 N 次相同结果才输出（折中：松开平滑/去抖以加快触发）
# 动作冷却：触发一次操作后，这么久内不再响应新操作（避免连续手势疯狂翻页/缩放）
ACTION_COOLDOWN_MS = 1150
# 视频快退/快进步长（毫秒）：左/右手势控制
SEEK_STEP_MS = 30000
# "已执行"提示时长（毫秒）：触发动作后右上角短暂提示，之后恢复显示
TOAST_MS = 800
# 锁存最长时长（毫秒）：超过则自动解锁。
# 这是**兜底**，正常的解锁靠"松手"（置信度掉下显示门槛）来触发。
# 别设太短：慢松手时模型可能持续读到同一个手势超过这个时长，
# 一超时就解锁 → 在新页面上又触发一次（实测踩过：首页单击进详情后
# 残留的单击被当成"确认"，直接弹回首页）。3500 覆盖了偏慢的松手动作。
MAX_LOCK_MS = 3500

# ---- 空闲降频（长时间识别不到手势时降低推理频率）----
# 思路：展台多数时间没人在做手势，而一次推理要几百毫秒，这段算力纯属白烧。
# 判据用**模型自己的输出**：最近一次 raw 置信度 >= CONFIDENCE_THRESHOLD 的时刻
# 记为"活跃"，之后越久没活跃就越降频。相比按画面帧差判断，这套不需要标定阈值、
# 不受现场光线与摄像头噪声影响，换任何环境行为一致。
#
# 阶梯：(已空闲毫秒, 推理间隔毫秒)，按空闲时长取最深的一档。
# 实测支撑：空场景下模型 raw 置信度中位 0.227、最大 0.491，从不达到 0.6；
# 真实手势能过 0.6 —— 两边分得很开，所以 0.6 这个判据是可靠的。
#
# 关于档位深浅：降得越深，越容易漏掉"访客走过来做的第一个手势"。
# 空闲间隔 1s 时，一个 1 秒长的手势必然会被覆盖到；到 5s 就只剩约 20% 命中率。
# 所以最深一档不建议超过 1~2s —— 空馆本身没人在乎，但"空馆状态下的第一个访客"
# 恰恰是最输不起的那次交互。
IDLE_LADDER_ENABLED = True
IDLE_LADDER = [
    (0,      20),      # 8s 内有过手势：全速，跟手
    (8000,   300),     # 空闲 8s：降频，最坏多等 0.3s（基本无感）
    (60000,  1000),    # 空闲 60s：空馆，最省；最坏多等 1s
]

# ---- 手势标签（IPN-Hand 13 类，对应 assets/gestures.json）----
# 完整标签码见 gesture_mapper.py 的 IPN_HAND_LABELS
GESTURE_LABELS: dict = {}


# ---- 现场可调参数（设置页滑条）----
# 这些值在运行期被直接读取（main_window 每次都读 config.X），改完立即生效，不用重启。
# 只有 SMOOTH_FRAMES 例外（它决定 deque 容量，在识别器构造时固定），故不列入。
TUNABLE: list = [
    {"key": "CONFIDENCE_THRESHOLD", "label": "触发置信度门槛",
     "min": 0.30, "max": 0.95, "decimals": 2,
     "hint": "低于此值的识别结果不触发任何操作。太低容易误触发，太高会变迟钝。"},
    {"key": "DISPLAY_CONFIDENCE", "label": "显示置信度门槛",
     "min": 0.10, "max": 0.80, "decimals": 2,
     "hint": "悬浮窗显示识别结果所需的最低置信度，低于则显示“无手势”。只影响显示。"},
    {"key": "CONSISTENCY_COUNT", "label": "去抖次数",
     "min": 1, "max": 6, "decimals": 0,
     "hint": "连续 N 次识别出同一动作才触发。调大更稳但更迟钝。"},
    {"key": "ACTION_COOLDOWN_MS", "label": "动作冷却",
     "min": 300, "max": 3000, "decimals": 0, "unit": "ms",
     "hint": "触发一次操作后的静默时间，防止一个手势被连读成多次翻页。"},
    {"key": "MAX_LOCK_MS", "label": "锁存上限",
     "min": 500, "max": 5000, "decimals": 0, "unit": "ms",
     "hint": "同一动作执行后锁定这么久，用户“松手”后才能再做一次。"},
    {"key": "DISPLAY_HOLD_MS", "label": "显示保持",
     "min": 0, "max": 3000, "decimals": 0, "unit": "ms",
     "hint": "手势消失后仍保留显示的时间，避免瞬时动态手势一闪就没。"},
]

# 本地调参文件：只有点“保存为默认”才会生成，不随版本库分发
LOCAL_CONFIG_PATH = os.path.join(ROOT_DIR, "config_local.json")

# 记录代码里的默认值（必须在应用本地覆盖之前抓取）
DEFAULTS: dict = {spec["key"]: globals()[spec["key"]] for spec in TUNABLE}


def _apply_local_overrides():
    """把 config_local.json 覆盖到本模块变量。文件不存在则全部用代码默认值。"""
    try:
        with open(LOCAL_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return
    except Exception as e:
        print(f"[Config] 读取 {os.path.basename(LOCAL_CONFIG_PATH)} 失败，改用默认值: {e}", flush=True)
        return

    applied = []
    for spec in TUNABLE:
        k = spec["key"]
        if k not in data:
            continue
        try:
            v = type(DEFAULTS[k])(data[k])       # 按默认值的类型转换，防止文件被改坏
        except Exception:
            continue
        # 夹到合法区间：坏文件不该把参数顶到离谱值而让展台失控
        v = max(spec["min"], min(spec["max"], v))
        globals()[k] = v
        applied.append(f"{k}={v}")
    if applied:
        print(f"[Config] 已应用本地调参（{os.path.basename(LOCAL_CONFIG_PATH)}）: "
              f"{', '.join(applied)}", flush=True)


def save_local_overrides() -> str:
    """把当前可调参数写入 config_local.json，下次启动自动生效。返回文件路径。"""
    data = {spec["key"]: globals()[spec["key"]] for spec in TUNABLE}
    with open(LOCAL_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return LOCAL_CONFIG_PATH


def reset_to_defaults():
    """恢复代码默认值，并删除本地调参文件。"""
    for k, v in DEFAULTS.items():
        globals()[k] = v
    try:
        os.remove(LOCAL_CONFIG_PATH)
    except FileNotFoundError:
        pass


# 末尾执行：本地覆盖必须等所有变量都定义好之后再生效
_apply_local_overrides()
