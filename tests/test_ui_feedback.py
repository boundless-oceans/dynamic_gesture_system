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
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QApplication, QStackedWidget, QWidget

from src import config
from src.ui.camera_widget import (ZONE_ALPHA_MAX, ZONE_ALPHA_MIN,
                                  ZONE_ALPHA_STATIC, zone_breath_alpha)
from src.ui.home_page import HomePage, sheen_progress
from src.ui.main_window import MainWindow
from src.ui.page_fade import PageFade
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


class _CountingFade(PageFade):
    """多记一个"被显示过几次"。

    "关掉过渡"的保证是**覆盖层从不出现**，而不是"最后不可见" ——
    后者不检查时长也能满足（show() 之后立刻被 Qt 收尾掉），靠不住。
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.show_count = 0

    def showEvent(self, event):
        self.show_count += 1
        super().showEvent(event)


class TestInkParticles(unittest.TestCase):
    """水墨粒子背景：只在页面可见时跑 + 颜色不每帧现造

    ⚠ 它是**整页重绘**，每 50ms 一次。展台 24 小时开着，所以"藏起来要停"
    和"别每帧白造对象"这两件都值得守。
    """

    def _make(self, cls=None):
        from src.ui.base_page import BasePage
        p = (cls or BasePage)()
        p.resize(640, 480)
        self._opened.append(p)
        return p

    def setUp(self):
        self._opened = []

    def tearDown(self):
        for p in self._opened:
            p.close()

    def test_粒子数跟着配置走(self):
        p = self._make()
        self.assertEqual(len(p._particles), config.INK_PARTICLE_COUNT)

    def test_透明度已经烘进颜色里(self):
        """透明度是一辈子不变的 —— 每帧现造 QColor + setAlphaF 纯属浪费。

        粒子 300 个、20fps，就是每秒 6000 个白造的对象。
        """
        p = self._make()
        for pt in p._particles:
            brush = pt['brush']
            a = brush.color().alphaF()
            self.assertGreaterEqual(a, 0.08 - 1e-6)
            self.assertLessEqual(a, 0.35 + 1e-6)
            self.assertGreater(brush.color().alpha(), 0, "透明度没烘进颜色里")

    def test_刚构造时定时器不跑(self):
        """⚠ 这是本条的由来：原先构造函数里无条件 start()，
        页面还没显示（甚至永远不会显示）就开始空转。"""
        p = self._make()
        self.assertFalse(p._timer.isActive(), "页面还没显示，粒子不该已经在跑")

    def test_显示后开始藏起来就停(self):
        p = self._make()
        p.show()
        _app.processEvents()
        self.assertTrue(p._timer.isActive(), "页面显示了，粒子应当跑起来")
        p.hide()
        _app.processEvents()
        self.assertFalse(p._timer.isActive(), "页面藏了粒子还在跑 —— 整页重绘，白烧 CPU")

    def test_三个继承页面都遵守这条(self):
        """⚠ 子类重写 showEvent / hideEvent 时若忘了调 super()，粒子的启停就断了：
        要么藏起来还在跑，要么显示了不动（画面一片死板）。
        """
        from src.ui.detail_page import DetailPage
        from src.ui.home_page import HomePage
        from src.ui.inheritor_page import InheritorPage
        for cls in (HomePage, DetailPage, InheritorPage):
            with self.subTest(page=cls.__name__):
                p = self._make(cls)
                p.show()
                _app.processEvents()
                self.assertTrue(p._timer.isActive(),
                                "%s 显示后粒子没跑 —— 重写 showEvent 忘了调 super()？"
                                % cls.__name__)
                p.hide()
                _app.processEvents()
                self.assertFalse(p._timer.isActive(),
                                 "%s 藏起来后粒子还在跑" % cls.__name__)

    def test_绘制不崩(self):
        p = self._make()
        p.show()
        _app.processEvents()
        self.assertFalse(p.grab().isNull(), "背景画不出来")


class _StubIdle:
    """假的"空闲多久"来源"""

    def __init__(self, ms):
        self.ms = ms

    def idle_ms(self):
        return self.ms


class TestIdleAwareParticles(unittest.TestCase):
    """粒子背景跟着"空闲多久"降频 —— 空馆时没人看，没必要还按 20fps 刷整页"""

    def setUp(self):
        from src.ui.base_page import BasePage
        self.page = BasePage()
        self.page.resize(640, 480)
        self._base = config.INK_PARTICLE_LADDER[0][1]

    def tearDown(self):
        self.page.close()

    def test_纯函数_没给空闲值就按正常速度(self):
        from src.ui.base_page import particle_interval_ms
        self.assertEqual(particle_interval_ms(None), self._base)

    def test_纯函数_各档取值(self):
        from src.ui.base_page import particle_interval_ms
        for threshold, ms in config.INK_PARTICLE_LADDER:
            self.assertEqual(particle_interval_ms(threshold), ms,
                             "空闲 %d ms 应当落在这一档" % threshold)
        self.assertEqual(particle_interval_ms(threshold - 1),
                         config.INK_PARTICLE_LADDER[-2][1] if len(
                             config.INK_PARTICLE_LADDER) > 1 else self._base,
                         "差 1ms 还没到下一档")

    def test_纯函数_再久也不会更快(self):
        from src.ui.base_page import particle_interval_ms
        deepest = config.INK_PARTICLE_LADDER[-1][1]
        for extra in (0, 10 ** 6, 10 ** 9):
            self.assertEqual(particle_interval_ms(config.INK_PARTICLE_LADDER[-1][0] + extra),
                             deepest)

    def test_没设来源就一直按正常速度(self):
        self.assertIsNone(self.page._idle_ms_fn)
        self.page._retune()
        self.assertEqual(self.page._timer.interval(), self._base)

    def test_空闲久了刷新变慢_有人操作立刻回到正常(self):
        src = _StubIdle(0)
        self.page.set_idle_source(src.idle_ms)
        self.assertEqual(self.page._timer.interval(), self._base)

        src.ms = config.INK_PARTICLE_LADDER[-1][0]
        self.page._retune()
        self.assertEqual(self.page._timer.interval(), config.INK_PARTICLE_LADDER[-1][1],
                         "空闲到最深一档了，粒子应当慢下来")

        src.ms = 0
        self.page._retune()
        self.assertEqual(self.page._timer.interval(), self._base,
                         "有人操作了应当立刻回到正常速度")

    def test_可以取消降频(self):
        self.page.set_idle_source(_StubIdle(10 ** 6).idle_ms)
        self.assertNotEqual(self.page._timer.interval(), self._base)
        self.page.set_idle_source(None)
        self.assertEqual(self.page._timer.interval(), self._base)

    def test_分档阈值与推理的空闲阶梯一致(self):
        """⚠ 两边是同一个"多久没人操作"的语义。

        阈值跑偏了就会出现"推理已经降频了、粒子还在满速刷"这种不一致 ——
        而这恰恰是省 CPU 的初衷。
        """
        self.assertEqual([t for t, _ in config.INK_PARTICLE_LADDER],
                         [t for t, _ in config.IDLE_LADDER])

    def test_分档表本身合法(self):
        ladder = config.INK_PARTICLE_LADDER
        self.assertTrue(ladder, "分档表不能是空的")
        self.assertEqual(ladder[0][0], 0,
                         "第一档必须从 0 开始，否则刚操作完的空闲值没有档可用")
        thresholds = [t for t, _ in ladder]
        self.assertEqual(thresholds, sorted(thresholds), "阈值必须递增")
        intervals = [m for _, m in ladder]
        self.assertEqual(intervals, sorted(intervals), "间隔必须随空闲递增（越闲越慢）")
        self.assertGreater(intervals[0], 0)


class TestIdleWiringToPages(unittest.TestCase):
    """`MainWindow._wire_idle_source` 把空闲来源交给**带粒子背景**的页面"""

    def test_只交给带粒子背景的页面(self):
        from src.ui.home_page import HomePage
        from src.ui.settings_page import SettingsPage
        home, settings = HomePage(), SettingsPage()
        try:
            stub = types.SimpleNamespace(pages={"home": home, "settings": settings},
                                         it=_StubIdle(12345))
            MainWindow._wire_idle_source(stub)
            self.assertIsNotNone(home._idle_ms_fn, "首页应当拿到空闲来源")
            self.assertEqual(home._idle_ms_fn(), 12345)
            self.assertFalse(hasattr(settings, "_idle_ms_fn"),
                             "设置页没有粒子背景（自己画的），不该被碰")
        finally:
            home.close(); settings.close()


class _FakeTime:
    """可控时钟。光条的相位是按真实时间算的，测试里必须握在手上。"""

    def __init__(self):
        self.ms = 0.0

    def time(self):
        return self.ms / 1000.0


class _HomeBase(unittest.TestCase):

    def setUp(self):
        self.page = HomePage()
        self.page.resize(1000, 700)
        self.page.show()
        _app.processEvents()

    def tearDown(self):
        self.page.close()


class TestCardSheenPure(_HomeBase):
    """光条的位置计算 —— 纯函数，直接喂时间戳"""

    def setUp(self):
        super().setUp()
        self._saved = (config.HOME_CARD_SHEEN, config.HOME_CARD_SHEEN_MS)
        config.HOME_CARD_SHEEN = True
        config.HOME_CARD_SHEEN_MS = 2800

    def tearDown(self):
        config.HOME_CARD_SHEEN, config.HOME_CARD_SHEEN_MS = self._saved
        super().tearDown()

    def test_周期起点从卡左外侧开始(self):
        self.assertEqual(sheen_progress(0), 0.0)

    def test_扫过期间一路向前(self):
        p = config.HOME_CARD_SHEEN_MS
        vals = [sheen_progress(p * f) for f in (0.0, 0.05, 0.1, 0.2, 0.3)]
        self.assertTrue(all(v is not None for v in vals), "扫过期间应当每一帧都画")
        self.assertEqual(vals, sorted(vals), "位置应当单调向前")

    def test_扫完就停一段(self):
        """停顿期不画 —— 既是为了"一闪而过"的观感，也省掉 2/3 的重绘"""
        p = config.HOME_CARD_SHEEN_MS
        self.assertIsNone(sheen_progress(p * 0.34))
        self.assertIsNone(sheen_progress(p * 0.6))
        self.assertIsNone(sheen_progress(p * 0.99))

    def test_下一个周期重新开始(self):
        p = config.HOME_CARD_SHEEN_MS
        self.assertEqual(sheen_progress(p), 0.0)
        self.assertEqual(sheen_progress(p * 3), 0.0)

    def test_位置始终在_0_1_之间(self):
        p = config.HOME_CARD_SHEEN_MS
        for i in range(200):
            v = sheen_progress(p * i / 61.0)
            if v is not None:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)

    def test_关掉开关就完全不画(self):
        config.HOME_CARD_SHEEN = False
        for f in (0.0, 0.1, 0.33, 0.8):
            self.assertIsNone(sheen_progress(config.HOME_CARD_SHEEN_MS * f))

    def test_周期非法时不崩也不画(self):
        config.HOME_CARD_SHEEN_MS = 0
        self.assertIsNone(sheen_progress(123))


class TestCardSheenWiring(_HomeBase):
    """光条真的画在**选中那张**上，而且**只在页面可见时**才刷新"""

    def setUp(self):
        super().setUp()
        self._mod = __import__("src.ui.home_page", fromlist=["time"])
        self._real_time = self._mod.time
        self.fake = _FakeTime()
        self._mod.time = self.fake
        self._saved = config.HOME_CARD_SHEEN
        config.HOME_CARD_SHEEN = True

    def tearDown(self):
        self._mod.time = self._real_time
        config.HOME_CARD_SHEEN = self._saved
        super().tearDown()

    def _spy_updates(self):
        called = []
        for i, c in enumerate(self.page._cards):
            c.update = (lambda i: (lambda *a: called.append(i)))(i)
        return called

    def test_只重绘选中那一张(self):
        """11 张卡每帧全刷一遍没必要 —— 只有选中的那张有光条"""
        self.fake.ms = 0.0                       # 周期起点，正在扫
        self.page._move(2)
        called = self._spy_updates()
        self.page._tick_sheen()
        self.assertEqual(called, [2], "应当只重绘选中的那一张")

    def test_停顿期不重绘(self):
        self.fake.ms = config.HOME_CARD_SHEEN_MS * 0.8
        self.page._move(0)
        self.page._sheen_live = False            # 上一帧也没画（已收过尾）
        called = self._spy_updates()
        self.page._tick_sheen()
        self.assertEqual(called, [], "停顿期不该重绘")

    def test_扫完补刷一帧(self):
        """⚠ 不补这一帧的话，最后一帧可能停在"光条刚探进卡里"的位置上，
        留下一条淡淡的竖边。"""
        self.page._move(0)
        self.fake.ms = 0.0
        self.page._tick_sheen()                  # 正在扫
        self.fake.ms = config.HOME_CARD_SHEEN_MS * 0.8
        called = self._spy_updates()
        self.page._tick_sheen()                  # 进入停顿
        self.assertEqual(called, [0], "扫完应当补刷一帧收尾")

    def test_页面藏起来就停止刷新(self):
        """⚠ 展台 24 小时开着 —— 没人看的时候不该一直重绘"""
        self.page.show()
        _app.processEvents()
        self.assertTrue(self.page._sheen.isActive(), "页面显示时应当刷新光条")
        self.page.hide()
        _app.processEvents()
        self.assertFalse(self.page._sheen.isActive(), "页面藏了还在刷 —— 白烧 CPU")

    def test_关掉效果就不启动刷新(self):
        saved = config.HOME_CARD_SHEEN
        config.HOME_CARD_SHEEN = False
        try:
            h = HomePage()
            h.resize(800, 600)
            h.show()
            _app.processEvents()
            self.assertFalse(h._sheen.isActive(), "关掉效果后不该再起刷新定时器")
            h.close()
        finally:
            config.HOME_CARD_SHEEN = saved

    def test_光条真的画上去了而且只画在选中那张上(self):
        self.page._move(0)
        self.fake.ms = config.HOME_CARD_SHEEN_MS * 0.17      # 扫到卡片中段
        sel_mid = self.page._cards[0].grab().toImage()
        other_mid = self.page._cards[1].grab().toImage()
        self.fake.ms = config.HOME_CARD_SHEEN_MS * 0.8       # 停顿
        sel_pause = self.page._cards[0].grab().toImage()
        other_pause = self.page._cards[1].grab().toImage()
        self.assertNotEqual(sel_mid, sel_pause, "选中卡上没看到光条")
        self.assertEqual(other_mid, other_pause, "没选中的卡上不该有光条")

    def test_绘制不崩(self):
        self.fake.ms = config.HOME_CARD_SHEEN_MS * 0.17
        for c in self.page._cards:
            self.assertFalse(c.grab().isNull())


class TestPageFade(unittest.TestCase):
    """换页过渡层本身"""

    def setUp(self):
        self._parents = []            # 父窗口必须留住引用，否则子控件的 C++ 对象被销毁

    def _make(self, cls=PageFade):
        parent = QWidget()
        parent.resize(400, 300)
        parent.show()
        self._parents.append(parent)
        return cls(parent)

    @staticmethod
    def _snapshot(color="#ff0000"):
        pm = QPixmap(400, 300)
        pm.fill(QColor(color))
        return pm

    def test_盖上快照后会显示(self):
        f = self._make()
        self.assertFalse(f.isVisible(), "没换页时不该显示")
        f.start(self._snapshot(), duration_ms=200)
        self.assertTrue(f.isVisible())
        self.assertGreater(f.opacity, 0.9, "应当从不透明开始淡出")

    def test_淡出结束后隐藏(self):
        """⚠ 这个覆盖层是一整张**不透明的快照**。

        一旦卡住不消失，整个界面看起来就是"死机" —— 而且不报任何错。
        """
        f = self._make()
        f.start(self._snapshot(), duration_ms=200)
        f._finish()                   # 模拟动画结束回调
        self.assertFalse(f.isVisible(), "过渡层没消失 —— 界面会看起来像死机")
        self.assertIsNone(f._snapshot)

    def test_关掉过渡时保持硬切(self):
        """`PAGE_FADE_MS = 0` 的保证是"覆盖层**从不出现**"。

        ⚠ 只断言"最后不可见"是不够的 —— 不检查时长的写法也会 `show()` 一下，
        然后被 Qt 对 0 时长动画的处理立刻收尾，最后**同样**是不可见。
        所以这里数的是"被显示过几次"。
        """
        f = self._make(_CountingFade)
        f.start(self._snapshot(), duration_ms=0)
        self.assertEqual(f.show_count, 0, "关掉过渡时不该显示覆盖层")
        self.assertFalse(f.isVisible())

    def test_空快照时什么都不做(self):
        f = self._make()
        f.start(None)
        self.assertFalse(f.isVisible())
        f.start(QPixmap())            # null pixmap
        self.assertFalse(f.isVisible(), "空快照不该盖上去（会是一片黑）")

    def test_不能挡住鼠标(self):
        """过渡只有几百毫秒，但挡住的话这几百毫秒里点哪儿都没反应"""
        f = self._make()
        self.assertTrue(f.testAttribute(Qt.WA_TransparentForMouseEvents))

    def test_连续两次不会把状态搞乱(self):
        f = self._make()
        f.start(self._snapshot("#ff0000"), duration_ms=200)
        f.start(self._snapshot("#00ff00"), duration_ms=200)
        self.assertTrue(f.isVisible())
        self.assertGreater(f.opacity, 0.9)

    def test_绘制不崩(self):
        f = self._make()
        f.grab()                      # 没有快照时应当直接跳过绘制
        f.start(self._snapshot(), duration_ms=200)
        self.assertFalse(f.grab().isNull(), "画不出来")


class _RecordingFade:
    """记录被交进来的快照"""

    def __init__(self):
        self.starts = []

    def start(self, snapshot, duration_ms=None):
        self.starts.append(snapshot)


class _PageChangeHarness:
    """只够跑 `MainWindow._on_page_changed` 的最小环境。

    用**真的** QStackedWidget 和真页面 —— 因为这里要验的正是"对旧页面 `grab()`
    拿到的到底是不是它自己那一页"，用假的就测不出东西了。
    """

    COLORS = ("#ff0000", "#00ff00", "#0000ff")

    def __init__(self):
        self.stack = QStackedWidget()
        self.stack.resize(320, 200)
        for col in self.COLORS:
            w = QWidget()
            w.setAutoFillBackground(True)
            pal = w.palette()
            pal.setColor(w.backgroundRole(), QColor(col))
            w.setPalette(pal)
            self.stack.addWidget(w)
        self.stack.setCurrentIndex(0)
        self.stack.show()
        self._prev_idx = 0
        self._lg = None
        self._gc = 0
        self.fade = _RecordingFade()
        # 这三个只被 raise_() 碰一下
        self.cw = QWidget(); self.bc = QWidget(); self.bs = QWidget()

    def switch_to(self, idx):
        self.stack.setCurrentIndex(idx)
        MainWindow._on_page_changed(self, idx)


class TestPageTransitionWiring(unittest.TestCase):
    """换页时**真的**取了旧页面的快照、并交给了过渡层。

    "算对了却没送进去"是这套 UI 最容易出的静默失效 —— 界面什么都不动，
    也不报错。所以单独守一条。
    """

    def setUp(self):
        self._h = _PageChangeHarness()

    def tearDown(self):
        self._h.stack.close()

    def test_换页会把旧页面快照交给过渡层(self):
        self._h.switch_to(2)
        self.assertEqual(len(self._h.fade.starts), 1, "换页没有触发过渡")
        self.assertFalse(self._h.fade.starts[0].isNull(), "交给过渡层的是空快照")

    def test_索引没变就不过渡(self):
        self._h.switch_to(0)          # 还在第 0 页
        self.assertEqual(self._h.fade.starts, [], "页面没换就不该过渡")

    def test_取的是旧页面而不是新页面(self):
        """⚠ 取错页面的后果很隐蔽：过渡看起来"有"，内容却是错的 —— 一闪而过。

        进入下一页时，覆盖层上应当是**上一页**的样子，淡出之后才露出新页面。
        """
        self._h.switch_to(1)          # 0 → 1，快照应当是第 0 页（红）
        self._h.switch_to(2)          # 1 → 2，快照应当是第 1 页（绿）
        self.assertEqual(len(self._h.fade.starts), 2)
        img = self._h.fade.starts[-1].toImage()
        self.assertEqual(
            img.pixelColor(img.width() // 2, img.height() // 2).name(), "#00ff00",
            "第二张快照取的不是上一页（第 1 页）")


if __name__ == "__main__":
    unittest.main(verbosity=2)
