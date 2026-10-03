"""操作反馈：屏幕下方的提示胶囊 + 交互区框的呼吸

这两样都是**纯视觉**的，所以测的不是"好不好看"，而是那些**坏了不会报错**的地方：

  * 提示算对了、却没真的送进胶囊控件（界面上什么都不显示）
  * 淡出结束时把**刚弹出来的新提示**一起藏掉
  * 胶囊挡住鼠标 —— 底下的按钮就点不到了
  * 呼吸的透明度跑出上下限，或者周期之间"跳"一下
  * 关掉呼吸开关时亮度变了（应当与加呼吸之前**完全一致**）

离屏运行，不需要显示器和摄像头。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from src import config
from src.ui.camera_widget import (ZONE_ALPHA_MAX, ZONE_ALPHA_MIN,
                                  ZONE_ALPHA_STATIC, zone_breath_alpha)
from src.ui.toast import ToastOverlay

_app = None


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication(sys.argv)


class TestZoneBreath(unittest.TestCase):
    """交互区框的呼吸透明度 —— 纯函数，直接喂时间戳"""

    def setUp(self):
        self._saved = (config.CAMERA_ZONE_BREATH, config.CAMERA_ZONE_BREATH_MS)
        config.CAMERA_ZONE_BREATH = True
        config.CAMERA_ZONE_BREATH_MS = 3000

    def tearDown(self):
        config.CAMERA_ZONE_BREATH, config.CAMERA_ZONE_BREATH_MS = self._saved

    def test_起止都落在最小值上(self):
        """周期首尾同值，所以周期与周期之间不会"跳"一下"""
        p = config.CAMERA_ZONE_BREATH_MS
        self.assertEqual(zone_breath_alpha(0), ZONE_ALPHA_MIN)
        self.assertEqual(zone_breath_alpha(p), ZONE_ALPHA_MIN)
        self.assertEqual(zone_breath_alpha(2 * p), ZONE_ALPHA_MIN)

    def test_半周期到最亮(self):
        p = config.CAMERA_ZONE_BREATH_MS
        self.assertEqual(zone_breath_alpha(p / 2), ZONE_ALPHA_MAX)

    def test_始终落在上下限之内(self):
        p = config.CAMERA_ZONE_BREATH_MS
        for i in range(0, 400):
            v = zone_breath_alpha(p * i / 37.0)      # 故意用不对齐的步长
            self.assertGreaterEqual(v, ZONE_ALPHA_MIN, "跑到下限之外了")
            self.assertLessEqual(v, ZONE_ALPHA_MAX, "跑到上限之外了")

    def test_前半程变亮后半程变暗(self):
        """证明它确实在"呼吸"，而不是一直亮着或一直暗着"""
        p = config.CAMERA_ZONE_BREATH_MS
        quarter = [zone_breath_alpha(p * t / 8.0) for t in range(4)]
        self.assertEqual(quarter, sorted(quarter), "前半程应当一路变亮")
        later = [zone_breath_alpha(p * (4 + t) / 8.0) for t in range(4)]
        self.assertEqual(later, sorted(later, reverse=True), "后半程应当一路变暗")

    def test_关掉开关时与加呼吸之前完全一致(self):
        """关掉应当是**真正的无变化**，而不是换了个亮度"""
        config.CAMERA_ZONE_BREATH = False
        for t in (0, 750, 1500, 2250, 3000, 123456):
            self.assertEqual(zone_breath_alpha(t), ZONE_ALPHA_STATIC)

    def test_周期非法时不崩也不闪(self):
        config.CAMERA_ZONE_BREATH_MS = 0
        self.assertEqual(zone_breath_alpha(123), ZONE_ALPHA_STATIC)


class TestToast(unittest.TestCase):

    def _make(self, w: int = 1280, h: int = 800):
        parent = QWidget()
        parent.resize(w, h)
        parent.show()          # 父窗口不显示的话，子控件的 isVisible() 恒为 False
        # ⚠ 必须留住父窗口的引用：它一旦被 GC，子控件的 C++ 对象会跟着销毁，
        # 之后再访问就是 "Internal C++ object already deleted"（建三个父窗口时必现）。
        self._parents.append(parent)
        return parent, ToastOverlay(parent)

    def setUp(self):
        self._parents = []

    @staticmethod
    def _shown(t, text="✔ 已执行：向右"):
        """弹出提示并**立刻定位到最终位置**。

        show_toast 会启动一段"上浮"动画，静止态停在起点（比最终位置低 14px）。
        测试里没有事件循环推它，所以先 place() 归位再断言坐标。
        """
        t.show_toast(text)
        t.place()
        return t

    def test_显示后可见且文本正确(self):
        _, t = self._make()
        self.assertFalse(t.isVisible(), "没收到动作时不该显示")
        t.show_toast("✔ 已执行：向右")
        self.assertTrue(t.isVisible())
        self.assertEqual(t.current_text(), "✔ 已执行：向右")

    def test_水平居中且贴近底部(self):
        parent, t = self._make()
        self._shown(t)
        centre = t.x() + t.width() / 2.0
        self.assertAlmostEqual(centre, parent.width() / 2.0, delta=1,
                               msg="没有水平居中")
        self.assertGreater(t.y(), parent.height() * 0.6,
                           "没贴在屏幕下方 —— 那样又回到'访客看不见'的老问题上了")
        self.assertLessEqual(t.y() + t.height(), parent.height(), "超出窗口底边了")

    def test_窗口变小后仍在窗口内(self):
        parent, t = self._make(1280, 800)
        self._shown(t)
        parent.resize(640, 400)
        t.place()
        self.assertGreaterEqual(t.x(), 0)
        self.assertGreaterEqual(t.y(), 0)
        self.assertLessEqual(t.y() + t.height(), 400)

    def test_字越多胶囊越宽(self):
        _, short = self._make()
        short.show_toast("✔ 已执行：向右")
        _, long_ = self._make()
        long_.show_toast("✔ 已执行：快退")
        _, longer = self._make()
        longer.show_toast("✔ 已执行：向右抛出到下一项")
        self.assertLess(short.width(), longer.width(),
                        "胶囊宽度没有跟着文字量走")

    def test_不能挡住鼠标(self):
        """它是盖在页面之上的 —— 挡住鼠标的话下面的按钮就点不到了"""
        _, t = self._make()
        self.assertTrue(t.testAttribute(Qt.WA_TransparentForMouseEvents))

    def test_淡出结束后隐藏(self):
        _, t = self._make()
        t.show_toast("✔ 已执行：向右")
        t._set_opacity(0.0)
        t._hide_if_faded()
        self.assertFalse(t.isVisible())

    def test_淡出期间来了新提示不会被一起藏掉(self):
        """淡出的 240ms 里若又执行了一次动作，`show_toast` 会把透明度拉回 1.0；
        这时收尾逻辑不能把**新提示**也隐藏了。"""
        _, t = self._make()
        t.show_toast("✔ 已执行：向右")
        t._fade_out()                 # 开始淡出
        t.show_toast("✔ 已执行：向左")  # 淡出途中又来了一个
        t._set_opacity(1.0)
        t._hide_if_faded()            # 模拟上一次淡出的收尾回调姗姗来迟
        self.assertTrue(t.isVisible(), "新提示被上一次的收尾回调误隐藏了")
        self.assertEqual(t.current_text(), "✔ 已执行：向左")

    def test_绘制不崩(self):
        _, t = self._make()
        t.grab()                      # 透明状态下应当直接跳过绘制
        t.show_toast("✔ 已执行：向右")
        t._set_opacity(1.0)
        self.assertFalse(t.grab().isNull(), "画不出来")


if __name__ == "__main__":
    unittest.main(verbosity=2)
