"""全局配置"""

import json
import os

from src import paths

# ---- 项目路径 ----
# 走 paths.app_dir() 而不是从 __file__ 推算：打包后 __file__ 指向只读的
# _internal/，内容文件（assets/ weights/）其实铺在 exe 旁边。详见 src/paths.py
ROOT_DIR = paths.app_dir()

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
# 动作触发门槛：低于则不触发操作。
#
# 0.6 → 0.8（2026-09）→ **0.6**（2026-10，评审后回调）
#
# 回调的缘由是**产品判断变了**：评审看过现场后定的调子是
# "我们眼里的误触，在外行眼里就是灵敏、准确、有科技感"。
# 现场实测（外接摄像头）也支持这个判断 —— 路人从两侧走过时确实可能被认成手势，
# 但**距离一远置信度就掉到 50% 以下**，够不到 0.6。
#
# ⚠ 代价要摆在明面上：**近距离**走过时置信度最高能到 0.8+（实测通过率 27.6%），
# 0.6 会把这些放进来。好在这是个**滑条**（设置页「触发置信度门槛」），
# 现场真发现会翻页，当场往上推即可，不用重新打包。
CONFIDENCE_THRESHOLD = 0.6
# 显示门槛：悬浮窗显示识别名所需的最低置信度（更低显示"无手势"）
# 0.35 → 0.6（2026-09）：实测"人在镜头前走过（不做手势）"会不断产生 0.4~0.8 的
# 识别结果，悬浮窗就跟着乱闪。这个门槛只管"显示什么"，提到 0.6 能明显减少闪烁。
# **但不可能完全不闪** —— 走路有 27.6% 的采样 ≥0.6，只能降低频率。
DISPLAY_CONFIDENCE = 0.6
# 显示保持：高置信手势消失后，仍保留显示这么久（毫秒），避免瞬时动态手势一闪就没
DISPLAY_HOLD_MS = 1000
# 显示切换门槛：想"抢走"当前显示改成另一个手势，新结果置信度需达到这个值；
# 否则保持当前显示（避免动作结束后被一个中等置信的错误类抢走）
# 0.6 → 0.8（2026-09）：它必须**高于显示门槛**才有意义。两者都 0.6 时，
# 任何 ≥0.6 的新结果都能立刻抢走当前显示 —— 标签会一直换来换去。
# 抬到 0.8 之后，0.6~0.8 的结果只在"当前没显示"时出现，抢不走已有的。
DISPLAY_SWITCH_CONFIDENCE = 0.8

# ---- 图像预处理 ----
INPUT_SIZE = 224              # 送入网络尺寸
SCALE_SIZE = 256              # 短边缩放
INPUT_MEAN = [0.485, 0.456, 0.406]
INPUT_STD = [0.229, 0.224, 0.225]

# ---- 摄像头 ----
CAMERA_INDEX = 0              # 手动指定时的摄像头索引（CAMERA_AUTO_SELECT=False 时生效）
# 自动选择摄像头：优先外接（通常索引 1+），没有外接时用自带（索引 0）
CAMERA_AUTO_SELECT = True
# 只枚举索引 0 ~ CAMERA_SCAN_MAX-1。
# 注意 OpenCV 给的是**索引**不是设备名，哪个索引对应哪个摄像头由系统枚举顺序决定，
# 代码无法指定"1 号一定是罗技"——能保证的只是"优先非 0 号（外接），0 号兜底（自带）"。
# 按现场设备数量设成 3（自带 + 罗技 + 备用）即可，多枚举没有收益还会拖慢启动。
CAMERA_SCAN_MAX = 3
# 热插拔检查间隔（毫秒）：当前用的是自带摄像头时，每隔这么久在后台探一次
# 有没有外接可用（探到就自动切过去）。用外接时不做检查——它已经是最优选择了。
CAMERA_UPGRADE_CHECK_MS = 5000
# 优先使用 DirectShow 后端。Windows 上 OpenCV 默认走 MSMF，而部分 USB 摄像头
# 在 MSMF 下光是"打开 + 设分辨率"就要几十秒（实测罗技外接：MSMF 38.8s / DSHOW 3.2s），
# 界面会长时间停在"摄像头未开启"，看起来像坏了。DSHOW 失败会自动回退默认后端。
CAMERA_PREFER_DSHOW = True
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
# 交互区框是否做"呼吸"（缓慢明暗）。
# 它静止不动时在画面里就是一条虚线，很容易被忽略；呼吸一下能勾住视线，
# 也显得整个系统"活着"。周期用 3 秒 —— 再快就像在报警了。
CAMERA_ZONE_BREATH = True
CAMERA_ZONE_BREATH_MS = 3000

# ---- 首页布局 ----
# 首页卡片区**上边界**要让开的高度（像素）—— 给右上角的摄像头悬浮窗腾地方。
# 悬浮窗由 main_window.resizeEvent 放在 (宽-340, 20)、尺寸 320×240，下沿是 260；
# 这里再留 16px 余量。
# ⚠ 改那行位置或改悬浮窗尺寸时，这里必须跟着改 —— 否则最右那张卡会被悬浮窗盖住。
HOME_TOP_RESERVE_PX = 276
# 底部要给「关闭摄像头 / 手势说明」两个按钮留的高度（它们贴在 height-30 一带）
HOME_BOTTOM_RESERVE_PX = 62
# 选中卡放大到基准尺寸的倍数。
# ⚠ 一排的**总宽预算是按这个倍数算的**（见 home_page.HomePage._relayout）：
#   所以无论选中哪一张，整排都不会被顶得位移。改这个值时要留意这个前提。
HOME_SELECTED_SCALE = 1.08
# 卡片宽高比（宽 / 高）。太小会显得又瘦又长，太大图会压扁。
HOME_CARD_ASPECT = 0.64

# ---- 帧缓冲 ----
FRAME_BUFFER_MAX = 32         # 缓冲最多存多少帧

# ---- 去抖 ----
# 连续 N 次相同结果才触发。**默认 1 = 一次即触发**（2026-10 评审后从 2 改来）。
#
# 留成可调项而不是删掉：现场万一觉得太跳，操作员能在设置页把它推回 2，
# 不用重新打包。**默认值 1 本身不引入任何延迟** —— 它是"一次即触发"，不是"关掉去抖"。
# （注意 N=1 时要配合 main_window._ocg 里那句安排，见那里的注释。）
CONSISTENCY_COUNT = 1
# 动作冷却：触发一次操作后，这么久内不再响应新操作（避免连续手势疯狂翻页/缩放）。
#
# **从"触发"那一刻起算**（2026-10 改；原先是从"访客松手"起算）。
# 从松手起算本意是挡 §1.5 那个坑，代价却是**每一次操作**都要多等"手放下的时间"
# —— 实测常 0.6~5 秒，于是 1.5 秒的冷却体感成了 2~6.5 秒。
# 现在那个坑改由"间隙"判定单独负责（见 main_window._on_result）：
# **触发条件必须先不成立一次**，才允许下一次触发。
ACTION_COOLDOWN_MS = 1500
# 视频快退/快进步长（毫秒）：左/右手势控制
SEEK_STEP_MS = 30000
# "已执行"提示时长（毫秒）：触发动作后在**屏幕下方居中**弹一下（src/ui/toast.py），
# 之后淡出。别设太短 —— 加淡入淡出后总可见时长约等于它再加 0.4 秒。
TOAST_MS = 800
# 换页过渡时长（毫秒）：在页面之上盖一层"上一页的快照"再让它淡出，
# 把硬切变成交叉淡入淡出。**设为 0 即关闭**（恢复硬切）。
# 几百毫秒就够 —— 再长会让人觉得"点了没反应"。
PAGE_FADE_MS = 260
# 等待"间隙"的最长时间（毫秒）。**这不是防误触，是防死锁。**
#
# 一次动作执行后，触发条件必须**先不成立一次**（平滑置信度掉到
# CONFIDENCE_THRESHOLD 以下）才允许下一次 —— 见 main_window._on_result。
# 万一模型对**静止画面**持续输出 ≥ 门槛的结果，就永远等不到这个"间隙"
# → 展台彻底不响应用户手势，而且不报错、看着一切正常。这个上限把最坏情况封住。
#
# 5000 → 3000（2026-10）：判据换成"平滑置信度掉下触发门槛"之后，间隙比原先
# （即时置信度掉下 0.35）容易等到得多，兜底也就不必留那么宽。
# 最坏情况 = 3000 + 冷却 1500 ≈ 4.5 秒（原先 5000 + 1500 = 6.5 秒）。
MAX_HOLD_MS = 3000

# ---- 空闲降频（长时间没人真正操作时降低推理频率）----
# 思路：展台多数时间没人在操作，而一次推理要几百毫秒，这段算力纯属白烧。
#
# **判据 = 最近一次"真的执行了动作"的时刻**（main_window 在闸门放行后调
# `InferenceThread.mark_active()`）。之后越久没执行过动作，档位越深。
#
# 为什么不用"模型输出了高置信手势"当判据（**曾经就是那样**）：
#   实测**访客在镜头前走过、不做任何手势，也有 15.5% 的采样 ≥0.8**。
#   于是路人一走就把空闲计时清零 —— 在"有人走动但没人互动"的博物馆常态下，
#   降频几乎不生效。而"执行过动作"才是"有人在真用"的语义信号。
#
# ⚠ 这条判据的**失效方向是危险的**：万一 mark_active() 没被调到（代码改坏了），
#   系统会永远认为空闲 → 永远降频 → 访客手势变迟钝，而且不报错。
#   所以专门写了用例守住它：tests/test_idle_ladder.py 的 TestActiveCriterion。
#
# 阶梯：(已空闲毫秒, 推理间隔毫秒)，按空闲时长取最深的一档。
# 第一档 8s → 10s（2026-09）：判据换了之后降频更容易触发，10s 是给
# "刚操作完、还在看"的访客留的全速余量。
#
# 关于档位深浅：降得越深，越容易漏掉"访客走过来做的第一个手势"。
# 空闲间隔 1s 时，一个 1 秒长的手势必然会被覆盖到；到 5s 就只剩约 20% 命中率。
# 所以最深一档不建议超过 1~2s —— 空馆本身没人在乎，但"空馆状态下的第一个访客"
# 恰恰是最输不起的那次交互。
IDLE_LADDER_ENABLED = True
IDLE_LADDER = [
    (0,      20),      # 10s 内执行过动作：全速，跟手
    (10000,  350),     # 空闲 10s：降频，最坏多等 0.35s（基本无感）
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
     "hint": "连续 N 次识别出同一动作才触发。1 = 一次即触发（默认）；嫌太灵敏往上调。"},
    {"key": "ACTION_COOLDOWN_MS", "label": "动作冷却",
     "min": 300, "max": 3000, "decimals": 0, "unit": "ms",
     "hint": "触发一次操作后、且用户松手后的静默时间，防止一个手势被连读成多次翻页。"},
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
