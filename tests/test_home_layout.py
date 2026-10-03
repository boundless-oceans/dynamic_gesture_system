"""首页两排布局：卡片顺序、导航、激活分发、响应式

这几种坏法**都不会报错**，只会让人"点错人"或"看着别扭"，所以单独守：

  * **扁平顺序的映射** —— 第 `len(PROJECTS)` 张卡必须是"传承人 0"而不是"项目 0"。
    算错之后界面看着完全正常，只是点谁都点错
  * **激活分发** —— 点第 4 位传承人必须发出 `3`。原先 `_enter_inheritor` 不带参数、
    从首页进来**永远停在第一位**，正是这个毛病
  * **选中卡把整排顶位移** —— 一排挤 8 张时最容易出，视觉上"点一下整排跳一下"
  * **卡片区没让开右上角的摄像头悬浮窗** —— 最右那张卡会被它盖住

离屏运行，不需要显示器和摄像头。
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from src import config
from src.core.project_data import INHERITORS, PROJECTS
from src.ui.home_page import HomePage
from src.ui.main_window import IDX, MainWindow

_app = None


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication(sys.argv)


def _need(n, what):
    if n < 1:
        raise unittest.SkipTest("没有%s，跳过" % what)


class _HomeBase(unittest.TestCase):

    def setUp(self):
        _need(len(PROJECTS) + len(INHERITORS), "卡片数据")
        # ⚠ 这些用例关心的是"卡片**最终**摆在哪、多大"，不是动画过程。
        #   不关掉缓动的话，`_move()` 之后卡片还停在起始尺寸上 ——
        #   断言会**假绿**（选中卡和普通卡一样大，也就"不重叠"、也"都在窗口内"）。
        #   缓动本身由 test_ui_feedback.py 的 TestSelectionEasing 负责。
        self._saved_anim = config.HOME_SELECT_ANIM_MS
        config.HOME_SELECT_ANIM_MS = 0
        self.page = HomePage()
        self.resize(1280, 800)

    def tearDown(self):
        config.HOME_SELECT_ANIM_MS = self._saved_anim
        self.page.close()

    def resize(self, w, h):
        self.page.resize(w, h)
        self.page.show()
        _app.processEvents()

    def positions(self):
        return [(c.x(), c.y()) for c in self.page._cards]


class TestCardsAreReallyOnScreen(_HomeBase):
    """卡片得**真的挂在首页上并显示出来**。

    ⚠ 这条是被一次真机截图逼出来的：`_ItemCard` 忘了传 `parent`，
    于是每张卡都是一个**独立的顶层窗口** —— `move()` 生效、`x()`/`width()` 都有值、
    坐标断言全过，但屏幕上**一张卡都看不到**。纯坐标测试拦不住这种坏法。
    """

    def test_每张卡都是首页的子控件(self):
        for i, c in enumerate(self.page._cards):
            self.assertIs(c.parent(), self.page,
                          "第 %d 张卡不是首页的子控件（会变成一个看不见的顶层窗口）" % i)

    def test_每张卡都可见(self):
        for i, c in enumerate(self.page._cards):
            self.assertTrue(c.isVisible(), "第 %d 张卡没显示出来" % i)

    def test_每张卡都在窗口范围内(self):
        for i, c in enumerate(self.page._cards):
            self.assertGreater(c.width(), 0, "第 %d 张卡宽度是 0" % i)
            self.assertGreater(c.height(), 0, "第 %d 张卡高度是 0" % i)
            self.assertTrue(self.page.rect().intersects(c.geometry()),
                            "第 %d 张卡落在首页窗口外面" % i)


class TestCardOrder(_HomeBase):
    """扁平顺序：第一排全是项目，第二排全是传承人"""

    def test_卡数跟着数据走不写死(self):
        self.assertEqual(self.page.card_count(), len(PROJECTS) + len(INHERITORS),
                         "卡片数应当等于项目数 + 传承人数（不写死 8）")

    def test_第一排是项目第二排是传承人(self):
        """⚠ 这是最容易算错的一处。映射错了界面看着完全正常，只是点谁都点错。"""
        n_p = len(PROJECTS)
        for i in range(n_p):
            self.assertEqual(self.page._kinds[i], ("project", i),
                             "第 %d 张卡应当是项目 %d" % (i, i))
        for j in range(len(INHERITORS)):
            self.assertEqual(self.page._kinds[n_p + j], ("inheritor", j),
                             "第 %d 张卡应当是传承人 %d（不是项目 0）" % (n_p + j, j))

    def test_每排张数取两排里长的那个(self):
        self.assertEqual(self.page._per_row, max(len(PROJECTS), len(INHERITORS)))


class TestNavigation(_HomeBase):
    """左 / 右 = 扁平顺序上环绕走一格；上 / 下 = 换排"""

    def test_左右环绕(self):
        n = self.page.card_count()
        self.page._move(n - 1)
        self.page._next()
        self.assertEqual(self.page.current_index(), 0, "最后一张再向右应回到第一张")
        self.page._prev()
        self.assertEqual(self.page.current_index(), n - 1, "第一张再向左应到最后一张")

    def test_第一排最右向右进第二排第一个(self):
        self.page._move(len(PROJECTS) - 1)
        self.page._next()
        self.assertEqual(self.page._kinds[self.page.current_index()],
                         ("inheritor", 0), "第一排最右向右应进第二排第一个")

    def test_第一排最左向左到第二排最后一个(self):
        self.page._move(0)
        self.page._prev()
        self.assertEqual(self.page._kinds[self.page.current_index()],
                         ("inheritor", len(INHERITORS) - 1),
                         "第一张向左应到第二排最后一个")

    def test_上下跨排(self):
        n_p = len(PROJECTS)
        self.page._move(1)
        self.page._down()
        self.assertEqual(self.page.current_index(), 1 + n_p, "向下应换到第二排同列")
        self.page._up()
        self.assertEqual(self.page.current_index(), 1, "向上应换回第一排同列")

    def test_第一排向上不动(self):
        self.page._move(2)
        self.page._up()
        self.assertEqual(self.page.current_index(), 2, "已经在第一排，向上不该动")

    def test_下面没有对位就不动(self):
        """两排不一样长时（现在 6 个 5 位），最长那排多出来的卡下面没有东西"""
        if len(PROJECTS) <= len(INHERITORS):
            self.skipTest("需要第一排比第二排长才有意义")
        self.page._move(len(PROJECTS) - 1)
        before = self.page.current_index()
        self.page._down()
        self.assertEqual(self.page.current_index(), before, "下面没有对位就不该动")


class TestActivate(_HomeBase):
    """手势"单击"要按卡片类型分发 —— 且要带上**各自的下标**"""

    def setUp(self):
        super().setUp()
        self.got = []
        self.page.item_selected.connect(lambda i: self.got.append(("project", i)))
        self.page.inheritor_selected.connect(lambda i: self.got.append(("inheritor", i)))

    def test_项目卡发项目索引(self):
        self.page._move(2)
        self.page.activate_current()
        self.assertEqual(self.got, [("project", 2)])

    def test_传承人卡发传承人索引(self):
        """⚠ 点第 4 位传承人必须发出 3，不是 0。

        原先首页只有"向右抛到头就进传承人页"，进来**永远停在第一位** ——
        现在第二排每位各是一张卡，索引必须跟着卡片走。
        """
        if len(INHERITORS) < 4:
            self.skipTest("传承人不足 4 位")
        self.page._move(len(PROJECTS) + 3)
        self.page.activate_current()
        self.assertEqual(self.got, [("inheritor", 3)], "点第 4 位传承人应当进第 4 位")

    def test_双击也是激活(self):
        self.page._on_double_flat(len(PROJECTS) + 1)
        self.assertEqual(self.got, [("inheritor", 1)])
        self.assertEqual(self.page.current_index(), len(PROJECTS) + 1, "双击应同时选中")


class TestResponsive(_HomeBase):
    """卡片尺寸跟着窗口走 —— 固定尺寸放到大屏幕上会显得很空"""

    def test_窗口变大卡片也变大(self):
        self.resize(1280, 800)
        small = self.page._cards[-1].width()
        self.resize(1920, 1080)
        self.assertGreater(self.page._cards[-1].width(), small,
                           "窗口变大了卡片却没变大")

    def test_选中卡更大(self):
        self.page._move(0)
        _app.processEvents()
        self.assertGreater(self.page._cards[0].width(), self.page._cards[1].width(),
                           "选中的卡应当更大")

    def test_选中卡不把整排顶位移(self):
        """一张卡变大不该连累其他卡 —— 否则点一下整排跟着挪，很晃眼。

        现在的摆法是"按列号算坐标"（不是流式布局），所以这一点天然成立；
        这条是**特征测试**：以后若改成按前一张的右边缘依次排（流式），它会拦下来。
        """
        n = self.page.card_count()
        self.page._move(0)
        _app.processEvents()
        before = self.positions()
        self.page._move(min(3, n - 1))
        _app.processEvents()
        after = self.positions()
        for i in range(n):
            if i in (0, min(3, n - 1)):
                continue               # 这两张本来就是"变化"的那一对
            self.assertEqual(before[i], after[i],
                             "切换选中把第 %d 张卡顶得位移了" % i)

    def test_选中卡不压到邻居(self):
        """放大后的卡必须**落在槽位之间的空隙里**，不许盖住旁边的卡。

        这是"变大"这个效果唯一会真的坏掉的方式 —— 盖住了看起来就是乱的。
        约束是 `基准宽 × (放大倍数-1) / 2 ≤ 槽间隙`；放大倍数调大、或一排塞更多张
        （基准宽变小、而间隙按窗口宽算不变）都可能把它顶破。
        """
        per = self.page._per_row
        for w, h in ((1024, 768), (1280, 800), (1920, 1080), (3840, 2160)):
            with self.subTest(size="%dx%d" % (w, h)):
                self.resize(w, h)
                for sel in range(self.page.card_count()):
                    self.page._move(sel)
                    _app.processEvents()
                    # ⚠ 必须**按排分组**再比 —— 两排的卡本来就上下叠在同一列上，
                    #   混在一起按 x 排会把"上下两张"当成"左右两张"而误报重叠。
                    for r in (0, 1):
                        row = sorted(self.page._cards[r * per:(r + 1) * per],
                                     key=lambda c: c.x())
                        for a, b in zip(row, row[1:]):
                            self.assertLessEqual(
                                a.x() + a.width(), b.x(),
                                "第 %d 排：选中第 %d 张时压到了右边那张" % (r + 1, sel))

    def test_卡片都在窗口内(self):
        for w, h in ((1024, 768), (1280, 800), (1920, 1080), (3840, 2160)):
            with self.subTest(size="%dx%d" % (w, h)):
                self.resize(w, h)
                self.page._move(0)          # 让第一排里有一张是"选中放大"的
                _app.processEvents()
                for i, c in enumerate(self.page._cards):
                    self.assertGreaterEqual(c.x(), 0, "第 %d 张卡跑到窗口左边外面了" % i)
                    self.assertLessEqual(c.x() + c.width(), w,
                                         "第 %d 张卡跑到窗口右边外面了" % i)


class TestAvoidsCameraOverlay(_HomeBase):
    """卡片区要让开右上角的摄像头悬浮窗，否则最右那张卡会被它盖住"""

    def test_上边界常量确实让开了悬浮窗(self):
        """悬浮窗由 main_window.resizeEvent 放在 (宽-340, 20)、尺寸 320×240，
        下沿是 260。两处必须同步 —— 改了那边没改这边，卡片就会被盖住。"""
        self.assertGreaterEqual(config.HOME_TOP_RESERVE_PX, 20 + 240,
                                "首页卡片区的上边界跑到摄像头悬浮窗上面去了")

    def test_没有卡压在悬浮窗那块区域上(self):
        self.resize(1280, 800)
        cam = (1280 - 340, 20, 320, 240)
        for i, c in enumerate(self.page._cards):
            overlap = (c.x() < cam[0] + cam[2] and c.x() + c.width() > cam[0]
                       and c.y() < cam[1] + cam[3] and c.y() + c.height() > cam[1])
            self.assertFalse(overlap, "第 %d 张卡和摄像头悬浮窗重叠了" % i)


class _Recorder:
    def __init__(self):
        self.calls = []

    def show_person(self, i):
        self.calls.append(("show_person", i))

    def setCurrentIndex(self, i):
        self.calls.append(("setCurrentIndex", i))


class TestEnterInheritorForwardsIndex(unittest.TestCase):
    """`MainWindow._enter_inheritor` 必须把**索引**转给传承人页

    原先它不带参数、永远进第一位 —— 首页第二排每位各一张卡之后，
    "点谁进谁"就靠这一句。
    """

    def _stub(self):
        return types.SimpleNamespace(pages={"inheritor": _Recorder()},
                                     stack=_Recorder())

    def test_带索引时进那一位(self):
        w = self._stub()
        MainWindow._enter_inheritor(w, 3)
        self.assertIn(("show_person", 3), w.pages["inheritor"].calls,
                      "从首页第二排进来必须停在第 4 位，不是第一位")
        self.assertIn(("setCurrentIndex", IDX["inheritor"]), w.stack.calls)

    def test_不给索引时进第一位(self):
        w = self._stub()
        MainWindow._enter_inheritor(w)
        self.assertIn(("show_person", 0), w.pages["inheritor"].calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
