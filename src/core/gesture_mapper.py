"""手势映射：83 类 DSTE-Net 输出 → 9 种控制手势"""

# 9 种控制手势（对应 DESIGN.md 中的手势映射表）
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

# EgoGesture 83 类 → 9 种控制手势的映射表
# key: EgoGesture 原始标签名（小写）
# value: 控制手势名
# 注：未在表中的手势不触发任何操作

EGO_TO_CONTROL = {
    # 方向滑动
    "swipe_left":    "swipe_left",
    "swipe_right":   "swipe_right",
    "swipe_up":      "swipe_up",
    "swipe_down":    "swipe_down",
    # 缩放
    "zoom_in":       "zoom_in",
    "zoom_out":      "zoom_out",
    # 点击
    "click":         "click",
    "double_click":  "click",
    # 手掌张开（回到首页）
    "palm":          "palm",
    # 画圈（旋转3D模型）
    "circle":        "circle",
}

# 原始索引到标签名的备用映射
# 训练用的 JSON 标注中 "labels" 数组顺序即为索引 → 标签名
# 占位，等拿到 training.json 后替换
INDEX_TO_LABEL: dict[int, str] = {}


def map_gesture(raw_label: str) -> str | None:
    """
    将 EgoGesture 原始标签映射为控制手势。
    不在映射表中的返回 None（不触发操作）。
    """
    return EGO_TO_CONTROL.get(raw_label.lower(), None)


def index_to_control(idx: int) -> str | None:
    """通过索引查找：先查标签名，再做映射"""
    if INDEX_TO_LABEL:
        label = INDEX_TO_LABEL.get(idx)
        if label:
            return map_gesture(label)
    # 没有标签表时，直接用索引作为字符串
    return map_gesture(str(idx))
