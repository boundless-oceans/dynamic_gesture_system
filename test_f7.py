"""测试 F7: 手势映射"""

from src.core.gesture_mapper import map_gesture, index_to_control, EGO_TO_CONTROL


def test_mapped_gestures():
    """已映射的手势应该返回对应控制手势"""
    assert map_gesture("swipe_left") == "swipe_left"
    assert map_gesture("SWIPE_RIGHT") == "swipe_right"  # 大小写不敏感
    assert map_gesture("zoom_in") == "zoom_in"
    assert map_gesture("click") == "click"
    assert map_gesture("double_click") == "click"  # 双击也映射到 click
    assert map_gesture("palm") == "palm"
    assert map_gesture("circle") == "circle"
    print("test_mapped_gestures passed")


def test_unmapped_gestures():
    """未映射的手势应该返回 None"""
    assert map_gesture("grab") is None
    assert map_gesture("fist") is None
    assert map_gesture("mute") is None
    assert map_gesture("") is None
    print("test_unmapped_gestures passed")


def test_index_mapping():
    """索引映射测试"""
    # 无标签表时，以字符串索引查找
    result = index_to_control(0)  # "0" 不在映射表中
    assert result is None
    print("test_index_mapping passed")


def test_all_control_gestures_covered():
    """确保 9 种控制手势都在映射表中"""
    mapped_values = set(EGO_TO_CONTROL.values())
    from src.core.gesture_mapper import CONTROL_GESTURES
    assert CONTROL_GESTURES == mapped_values, \
        f"缺失控制手势: {CONTROL_GESTURES - mapped_values}"
    print("test_all_control_gestures_covered passed")


if __name__ == "__main__":
    test_mapped_gestures()
    test_unmapped_gestures()
    test_index_mapping()
    test_all_control_gestures_covered()
    print("All F7 tests passed!")
