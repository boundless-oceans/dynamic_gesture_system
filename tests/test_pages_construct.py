"""页面构造冒烟：所有页面（含 WebEngine 页）都能建起来

离屏运行，不需要显示器和摄像头。覆盖的是"导入/构造期"的破坏——
改了某个页面的构造函数签名、漏了依赖、素材路径写错，在这里就会炸。
（旧版是根目录的 test_all.py / test_mw.py，只能手工跑。）
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # 无显示器也能跑

from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget

_app = None

PAGES = [
    ("src.ui.home_page", "HomePage"),
    ("src.ui.detail_page", "DetailPage"),
    ("src.ui.settings_page", "SettingsPage"),
    ("src.ui.inheritor_page", "InheritorPage"),
    ("src.ui.viewer_page", "ViewerPage"),
    ("src.ui.camera_widget", "CameraWidget"),
]


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication(sys.argv)


def _build(module, cls):
    mod = __import__(module, fromlist=[cls])
    widget = getattr(mod, cls)()
    _app.processEvents()
    return widget


class TestPagesConstruct(unittest.TestCase):

    def test_所有页面可构造(self):
        for module, cls in PAGES:
            with self.subTest(page=cls):
                self.assertIsNotNone(_build(module, cls))

    def test_详情页可切遍所有项目(self):
        """切项目会重建整棵页面，历史上这里泄漏过控件和播放器"""
        d = _build("src.ui.detail_page", "DetailPage")
        from src.core.project_data import PROJECTS
        for i in range(len(PROJECTS)):
            with self.subTest(project=i):
                d.set_project(i)
                _app.processEvents()
                self.assertEqual(d.stack.count(), 2, "重建后应恰好是主视图 + 未分子页")

    def test_设置页滑条数量与可调项一致(self):
        from src import config
        sp = _build("src.ui.settings_page", "SettingsPage")
        self.assertEqual(len(sp._sliders), len(config.TUNABLE))

    def test_手势对照表每行列数与表头一致(self):
        """表头与每行的列数必须对得上。

        Qt **不报这个错** —— 多出来的格子被静默丢弃、少了的留白，
        表面上看只是"表有点怪"。增删列时最容易漏掉某一行（删「地图」那列就是），
        所以单独守一条结构性断言。
        """
        from src.ui import settings_page as sp
        for rows, headers, what in ((sp._ROWS, sp._HEADERS, "动态"),
                                    (sp._STATIC_ROWS, sp._STATIC_HEADERS, "静态")):
            self.assertTrue(rows, f"{what}手势表不该是空的")
            for row in rows:
                with self.subTest(表=what, 手势=row[0]):
                    self.assertEqual(len(row), len(headers),
                                     "这一行的列数与表头对不上：%r" % (row,))

    def test_手势说明页有两张表(self):
        """动态一张、静态一张。

        静态那两个（OK / 点赞）**不跟页面走**，塞进按页面分列的那张表里
        只能给每一列都填同一个动作，读起来更乱 —— 所以是分开的两张。
        """
        sp = _build("src.ui.settings_page", "SettingsPage")
        tables = sp.findChildren(QTableWidget)
        self.assertEqual(len(tables), 2, "手势说明页应当有动态、静态两张对照表")

    def test_设置页有返回首页按钮且真的接到信号上(self):
        """⚠ 这条是被一次真实事故逼出来的。

        加 `show_gestures()` 时它被插进了 `_setup_ui` 的中间，于是后面那段
        导航按钮的代码**整块被切进了新方法里** —— 页面**照样能构造**
        （构造期一声不响），只是"返回首页"按钮整个消失了。
        上面那条 `test_所有页面可构造` 拦不住这种坏法，要真的点一下才看得出来。
        """
        sp = _build("src.ui.settings_page", "SettingsPage")
        got = []
        sp.go_home.connect(lambda: got.append(1))
        buttons = [b for b in sp.findChildren(QPushButton) if b.text() == "返回首页"]
        self.assertTrue(buttons, "设置页没有「返回首页」按钮")
        buttons[0].click()
        self.assertEqual(got, [1], "「返回首页」按钮没接到 go_home 信号上")

    def test_设置页滑条初值等于config当前值(self):
        from src import config
        sp = _build("src.ui.settings_page", "SettingsPage")
        for spec in config.TUNABLE:
            scale = 10 ** spec["decimals"]
            expect = int(getattr(config, spec["key"]) * scale)
            self.assertEqual(sp._sliders[spec["key"]][0].value(), expect,
                             f"{spec['key']} 滑条初值与 config 不一致")


@unittest.skipUnless(
    os.path.exists(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "weights",
                                "TSQ_ipnhand_RGB_resnet50_shift0.50_blockres_avg_segment8_e50.pth")),
    "权重未随版本库分发（.gitignore），跳过主窗口构造")
class TestMainWindowConstruct(unittest.TestCase):
    """主窗口构造会真的搭一遍 ResNet-50 并加载权重，约 10 秒——但它是最有价值的一道冒烟。"""

    @classmethod
    def setUpClass(cls):
        from src.ui.main_window import MainWindow
        cls.win = MainWindow()          # 建一次，几条用例共用（构造很贵）
        _app.processEvents()

    @classmethod
    def tearDownClass(cls):
        cls.win.close()

    def test_主窗口可构造且权重状态正常(self):
        self.assertEqual(self.win.recognizer.status, "ok",
                         f"权重状态异常: {self.win.recognizer.status} "
                         f"{self.win.recognizer.status_detail}")

    def test_静态手势权重状态正常(self):
        """静态权重没随版本库分发（.gitignore）。缺失时应当是 missing，**不是崩**。"""
        self.assertIn(self.win.static.status, ("ok", "missing"),
                      f"静态手势状态异常: {self.win.static.status} "
                      f"{self.win.static.status_detail}")

    def test_静态手势接线真的通(self):
        """架构 A 的**端到端**接线：喂一条 ok 的静态结果，主窗口真的回首页。

        ⚠ 闸门逻辑本身由 tests/test_gesture_gate.py 用桩验（快、可控时钟）。
        这里验的是**另一件事**：真实 MainWindow 上的接线有没有漏 ——
        `self.static` 建了没、`cw.set_static` 在不在、设置页有没有 `show_gestures`。
        这类漏掉**不报错**，只是那个手势永远不生效。
        """
        from src import config
        from src.ui.main_window import IDX

        def feed(label, conf):
            for _ in range(config.STATIC_CONSISTENCY):
                self.win._on_result({"gesture": "0", "confidence": 0.0,
                                     "raw_gesture": "0", "raw_confidence": 0.0,
                                     "static": {"label": label, "confidence": conf}})
                _app.processEvents()

        # 从详情页出发，"回首页"才看得出来
        self.win.stack.setCurrentIndex(IDX["detail"])
        self.win._cooldown_until = 0.0
        _app.processEvents()
        feed("ok", 0.99)
        self.assertEqual(self.win.stack.currentIndex(), IDX["home"], "OK 手势没回首页")

        # 比耶 → 设置页，且必须先把标签页切到「手势说明」
        self.win.pages["settings"]._tabs.setCurrentIndex(1)   # 先人为停在「参数调节」
        self.win._cooldown_until = 0.0
        self.win._static_need_gap = False
        feed("peace", 0.99)
        self.assertEqual(self.win.stack.currentIndex(), IDX["settings"])
        self.assertEqual(self.win.pages["settings"]._tabs.currentIndex(), 0,
                         "进设置页时没把标签页切到「手势说明」")

        # 但在 3D 页上比耶要让位给动态模型的「旋转模型」
        self.win.stack.setCurrentIndex(IDX["viewer"])
        self.win._cooldown_until = 0.0
        self.win._static_need_gap = False
        self.win._static_lg = None
        self.win._static_count = 0
        feed("peace", 0.99)
        self.assertEqual(self.win.stack.currentIndex(), IDX["viewer"],
                         "3D 页上比耶不该跳去手势说明页（那一页的两指是旋转模型）")

    def test_没绑定的静态类不产生任何动作(self):
        """端到端再确认一次"弃权" —— 架构 A 的安全感全在这上面。"""
        from src.ui.main_window import IDX
        self.win.stack.setCurrentIndex(IDX["home"])
        self.win._cooldown_until = 0.0
        before = self.win.stack.currentIndex()
        for _ in range(3):
            self.win._on_result({"gesture": "0", "confidence": 0.0,
                                 "raw_gesture": "0", "raw_confidence": 0.0,
                                 "static": {"label": "palm", "confidence": 0.99}})
        self.assertEqual(self.win.stack.currentIndex(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
