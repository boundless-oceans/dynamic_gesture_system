"""手势映射：IPN-Hand 13 类 DSTE-Net 输出 → 控制手势

IPN-Hand 13 类（索引 0~12，取官方 id 顺序，排除 D0X 无手势类）：
    B0A 单指指向   B0B 双指指向
    G01 单击       G02 双指点击
    G03 向上抛出   G04 向下抛出   G05 向左抛出   G06 向右抛出
    G07 张开两次   G08 双击       G09 双指双击
    G10 放大       G11 缩小
"""

# 13 种控制手势（对应 DESIGN.md 中的手势映射表）
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
    "G05": "向左抛出", "G06": "向右抛出",
    "G07": "张开两次", "G08": "双击", "G09": "双指双击",
    "G10": "放大",     "G11": "缩小",
}

# IPN-Hand 标签码 → 控制手势（未列入的手势不触发任何操作）
# 设计语义：方向抛出≈滑动、单击/双击≈click、张开两次≈手掌(palm)回家、
# 放大/缩小≈zoom
IPN_TO_CONTROL: dict[str, str] = {
    # 方向滑动
    "G03": "swipe_up",
    "G04": "swipe_down",
    "G05": "swipe_left",
    "G06": "swipe_right",
    # 点击（单击 / 双击均视作 click）
    "G01": "click",
    "G08": "click",
    # 手掌张开（回到首页）
    "G07": "palm",
    # 缩放
    "G10": "zoom_in",
    "G11": "zoom_out",
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
