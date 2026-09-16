"""手势映射：IPN-Hand 13 类索引 → 控制手势

索引顺序与权重文件强绑定（模型输出第 i 维对应哪个手势），
一旦改动，识别结果会整体错位且**看起来仍在正常工作**，
所以这里把顺序和映射都钉死。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.gesture_mapper import (
    CONTROL_GESTURES,
    IPN_HAND_LABELS,
    IPN_LABEL_CN,
    IPN_TO_CONTROL,
    index_to_control,
    label_cn,
    label_of,
)


class TestLabelOrder(unittest.TestCase):

    def test_索引顺序等于官方id顺序(self):
        self.assertEqual(IPN_HAND_LABELS, [
            "B0A", "B0B", "G01", "G02", "G03", "G04", "G05",
            "G06", "G07", "G08", "G09", "G10", "G11",
        ])
        self.assertEqual(len(IPN_HAND_LABELS), 13)

    def test_索引与标签码互查(self):
        self.assertEqual(label_of(0), "B0A")
        self.assertEqual(label_of(12), "G11")
        self.assertIsNone(label_of(13))
        self.assertIsNone(label_of(-1))

    def test_中文名(self):
        self.assertEqual(label_cn(2), "单击")
        self.assertTrue(label_cn(99).startswith("ID:"), "越界应给占位文本而不是抛异常")

    def test_每个标签码都有中文名(self):
        for code in IPN_HAND_LABELS:
            self.assertIn(code, IPN_LABEL_CN, f"{code} 缺少中文显示名")


class TestMapping(unittest.TestCase):

    def test_四个方向抛出(self):
        # 因镜像输入：G05 在画面里是向右，等于用户向右抛出
        self.assertEqual(index_to_control(4), "swipe_up")      # G03
        self.assertEqual(index_to_control(5), "swipe_down")    # G04
        self.assertEqual(index_to_control(6), "swipe_right")   # G05
        self.assertEqual(index_to_control(7), "swipe_left")    # G06

    def test_动作类(self):
        self.assertEqual(index_to_control(2), "click")         # G01 单击
        self.assertEqual(index_to_control(8), "zoom_in")       # G07 张开两次
        self.assertEqual(index_to_control(12), "zoom_out")     # G11 缩小
        self.assertEqual(index_to_control(9), "circle")        # G08 双击

    def test_偏弱类别刻意不绑定(self):
        """B0A/B0B/G02/G09/G10 实测偏弱或易混，不绑定 → 误判也不会产生动作"""
        for idx in (0, 1, 3, 10, 11):
            self.assertIsNone(index_to_control(idx), f"索引 {idx} 不应绑定控制手势")

    def test_越界返回None(self):
        self.assertIsNone(index_to_control(13))
        self.assertIsNone(index_to_control(-1))

    def test_映射值必须是已声明的控制手势(self):
        self.assertTrue(IPN_TO_CONTROL, "映射表不应为空")
        for code, ctrl in IPN_TO_CONTROL.items():
            self.assertIn(ctrl, CONTROL_GESTURES, f"{code} -> {ctrl} 不是合法控制手势")

    def test_映射的键都必须是真实标签码(self):
        for code in IPN_TO_CONTROL:
            self.assertIn(code, IPN_HAND_LABELS, f"{code} 不在标签表里")

    def test_不绑定palm(self):
        """回首页已改用按钮。历史上设置页曾列着 palm，误导使用者。"""
        self.assertNotIn("palm", IPN_TO_CONTROL.values())


if __name__ == "__main__":
    unittest.main(verbosity=2)
