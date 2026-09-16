"""测试 F7: 手势映射（IPN-Hand 13 类 → 控制手势）"""

from src.core.gesture_mapper import (
    IPN_HAND_LABELS,
    IPN_TO_CONTROL,
    CONTROL_GESTURES,
    index_to_control,
    label_of,
    label_cn,
)


def test_label_order():
    """索引顺序 = IPN-Hand 官方 id 顺序（排除 D0X 无手势类）"""
    assert IPN_HAND_LABELS == [
        "B0A", "B0B", "G01", "G02", "G03", "G04", "G05",
        "G06", "G07", "G08", "G09", "G10", "G11",
    ]
    assert len(IPN_HAND_LABELS) == 13
    # 索引 → 标签码
    assert label_of(0) == "B0A"
    assert label_of(12) == "G11"
    assert label_of(13) is None
    assert label_of(-1) is None
    # 中文名可用（显示用）
    assert label_cn(2) == "单击"
    assert label_cn(99).startswith("ID:")
    print("test_label_order passed")


def test_direction_mapping():
    """方向抛出 → 对应滑动"""
    assert index_to_control(4) == "swipe_up"      # G03 向上抛出
    assert index_to_control(5) == "swipe_down"    # G04 向下抛出
    assert index_to_control(6) == "swipe_left"    # G05 向左抛出
    assert index_to_control(7) == "swipe_right"   # G06 向右抛出
    print("test_direction_mapping passed")


def test_action_mapping():
    """单击→click，张开两次→zoom_in，缩小→zoom_out，双击→circle(旋转)"""
    assert index_to_control(2) == "click"          # G01 单击 → 进入详情
    assert index_to_control(8) == "zoom_in"        # G07 张开两次 → 放大
    assert index_to_control(12) == "zoom_out"      # G11 缩小
    assert index_to_control(9) == "circle"         # G08 双击 → 旋转
    print("test_action_mapping passed")


def test_unmapped():
    """未绑定控制手势的类别/越界返回 None"""
    assert index_to_control(0) is None   # B0A 单指指向
    assert index_to_control(1) is None   # B0B 双指指向
    assert index_to_control(3) is None   # G02 双指点击
    assert index_to_control(10) is None  # G09 双指双击（备用，不绑定）
    assert index_to_control(11) is None  # G10 放大（偏弱，不绑定）
    assert index_to_control(13) is None  # 越界
    assert index_to_control(-1) is None  # 越界
    print("test_unmapped passed")


def test_control_gestures_valid():
    """所有映射值都必须是已声明的控制手势"""
    assert IPN_TO_CONTROL, "映射表不应为空"
    for code, ctrl in IPN_TO_CONTROL.items():
        assert ctrl in CONTROL_GESTURES, f"{code} -> {ctrl} 不是合法控制手势"
    print("test_control_gestures_valid passed")


if __name__ == "__main__":
    test_label_order()
    test_direction_mapping()
    test_action_mapping()
    test_unmapped()
    test_control_gestures_valid()
    print("All F7 tests passed!")
