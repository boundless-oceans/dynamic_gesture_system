"""手势映射：IPN-Hand 13 类 DSTE-Net 输出 → 控制手势

IPN-Hand 13 类（索引 0~12，取官方 id 顺序，排除 D0X 无手势类）：
    B0A 单指指向   B0B 双指指向
    G01 单击       G02 双指点击
    G03 向上抛出   G04 向下抛出   G05 向左抛出   G06 向右抛出
    G07 张开两次   G08 双击       G09 双指双击
    G10 放大       G11 缩小
"""

# 控制动作的取值集合（哪些控制手势是合法的）
# 注：这里只是合法值清单，**不是**"哪个手势映射到哪个动作"——那张表在下面的
# IPN_TO_CONTROL，各页面怎么响应的真值在 main_window.MainWindow._ocg。
CONTROL_GESTURES = {
    "swipe_left",
    "swipe_right",
    "swipe_up",
    "swipe_down",
    "click",
    "palm",
    "zoom_in",
    "zoom_out",
    "circle",
}

# 索引 0~12 → IPN-Hand 标签码（训练 json labels 数组顺序，官方 id 顺序）
IPN_HAND_LABELS: list[str] = [
    "B0A", "B0B", "G01", "G02", "G03", "G04", "G05",
    "G06", "G07", "G08", "G09", "G10", "G11",
]

# IPN-Hand 标签码 → 中文显示名（与 assets/gestures.json 保持一致）
IPN_LABEL_CN: dict[str, str] = {
    "B0A": "单指指向", "B0B": "双指指向",
    "G01": "单击",     "G02": "双指点击",
    "G03": "向上抛出", "G04": "向下抛出",
    "G05": "向右抛出", "G06": "向左抛出",
    "G07": "张开两次", "G08": "双击", "G09": "双指双击",
    "G10": "放大",     "G11": "缩小",
}

# IPN-Hand 标签码 → 控制手势（未列入的手势不触发任何操作）
#
# 设计原则：**只绑定实测可靠的类**。依据是服务器测试集上的逐类准确率
# （`test_models.py --test_segments=8`，整体 89.06%，类平均 83.44%）：
#
#     B0B 0.989   G06 0.981   G05 0.981   B0A 0.973   G04 0.942   G10 0.942
#     G07 0.904   G03 0.846   G11 0.769   G02 0.750   G01 0.712
#     G08 0.577   G09 0.481
#
# 但**准确率高不等于能绑** —— 还得看"非手势动作会不会被误认成它"。
# 在镜头前走路（58 次采样）实测：
#     B0A 被误认 24.1%（走路最易被认成的类）   G02 13.8%   B0B 0%
# 所以 B0A 虽然准（0.973）也不能用 —— 而且"指着屏幕"本来就是访客很自然的动作。
#
# 同理**"点击族"（G01/G02/G08/G09）整体不碰**：它们都是"敲一下"，
# 彼此只差手指数量和敲的次数，互相误判是必然的。而 G01 绑的是"确认"，
# 所以让 G08（双击）参与控制 = 访客做双击很可能触发"确认"这个错动作。
#
# 回首页不再占用手势，改用按钮。
IPN_TO_CONTROL: dict[str, str] = {
    # 首页导航（注意：因镜像输入，G05=画面向右=用户向右抛出）
    "G05": "swipe_right",    # 向右抛出 → 下一项/下一位
    "G06": "swipe_left",     # 向左抛出 → 上一项
    # 方向（传承人页=翻页；地图页=平移）
    "G03": "swipe_up",       # 向上抛出
    "G04": "swipe_down",     # 向下抛出
    # 确认（所有页面：激活当前选中项）
    "G01": "click",          # 单击 ← 0.712，偏弱，但"确认"没有更可靠的替代
    # 3D 查看页
    "G07": "zoom_in",        # 张开两次 → 放大
    "G11": "zoom_out",       # 缩小 ← 0.769，偏弱
    "B0B": "circle",         # 双指指向 → 旋转模型
}


# 控制动作 → 中文短语（用于"已执行"提示）
CONTROL_CN: dict[str, str] = {
    "swipe_left": "向左",
    "swipe_right": "向右",
    "swipe_down": "向下",
    "click": "确认",
    "zoom_in": "放大",
    "zoom_out": "缩小",
    "circle": "旋转",
    "palm": "返回首页",
}


def label_of(idx: int) -> str | None:
    """索引 → IPN-Hand 标签码，越界返回 None"""
    if 0 <= idx < len(IPN_HAND_LABELS):
        return IPN_HAND_LABELS[idx]
    return None


def label_cn(idx: int) -> str:
    """索引 → 中文手势名，越界返回占位文本"""
    code = label_of(idx)
    return IPN_LABEL_CN.get(code, f"ID:{idx}")


def index_to_control(idx: int) -> str | None:
    """索引 → 控制手势，未绑定任何控制手势的类别返回 None"""
    code = label_of(idx)
    if code is None:
        return None
    return IPN_TO_CONTROL.get(code, None)
