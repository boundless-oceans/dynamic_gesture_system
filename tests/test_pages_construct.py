"""页面构造冒烟：所有页面（含 WebEngine 页）都能建起来

离屏运行，不需要显示器和摄像头。覆盖的是"导入/构造期"的破坏——
改了某个页面的构造函数签名、漏了依赖、素材路径写错，在这里就会炸。
（旧版是根目录的 test_all.py / test_mw.py，只能手工跑。）
"""
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # 无显示器也能跑

from PySide6.QtWidgets import QApplication, QPushButton, QTableWidget, QWidget

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


class TestLikeReset(unittest.TestCase):
    """设置页里的「清空点赞计数」

    清空**不可逆**（没有任何别的地方能恢复），所以两条都得守：

      * **没确认就绝不能清** —— 这是会毁掉长期数据的一步
      * **清完之后要把信号发出去** —— 否则首页角标还留着已经删掉的数字，
        屏幕上跟存档对不上，而且没人会发现
    """

    def setUp(self):
        from src.core.like_store import LikeStore
        self.sp = _build("src.ui.settings_page", "SettingsPage")
        self.dir = tempfile.mkdtemp(prefix="likes-reset-")
        self.store = LikeStore(os.path.join(self.dir, "likes.json"))
        self.sp.set_like_store(self.store)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_汇总跟着计数走(self):
        self.assertIn("还没有", self.sp._like_summary.text())
        self.store.add("proj:baogong", 3)
        self.store.add("inh:李绩", 2)
        self.sp.refresh_like_summary()
        t = self.sp._like_summary.text()
        self.assertIn("已有 2 项", t)
        self.assertIn("共 5 次", t)

    def test_确认框选否就不清(self):
        self.store.add("proj:baogong", 3)
        self.sp._ask = lambda *a: False
        self.sp._on_reset_likes()
        self.assertEqual(self.store.count("proj:baogong"), 3, "还没确认就把数据清了")
        self.assertNotIn("已清空", self.sp._like_status.text())

    def test_确认之后清空并发信号(self):
        self.store.add("proj:baogong", 3)
        got = []
        self.sp.likes_reset.connect(lambda: got.append(1))
        self.sp._ask = lambda *a: True
        self.sp._on_reset_likes()
        self.assertEqual(self.store.all_counts(), {})
        self.assertEqual(got, [1], "清完之后没通知出去 → 首页角标不会更新")
        self.assertIn("已清空", self.sp._like_status.text())
        self.assertIn("还没有", self.sp._like_summary.text())

    def test_确认框不能是黑底(self):
        """⚠ **真实踩过**：主窗口在页面容器上设过 `background: transparent`，
        而 **Qt 的样式表会传给子控件** —— QMessageBox 是设置页的子窗口，
        底色跟着变透明，在 Windows 上渲染成**一片纯黑**（实测平均亮度 229 → 3.8）。
        按钮在哪都看不见，操作员根本没法确认，表现就是**"清空按钮点了没反应"**。

        光读代码看不出来（`QMessageBox.question` 写得好好的），
        要把它 `grab()` 出来比像素。
        """
        host = QWidget()
        host.setStyleSheet("background: transparent;")     # 模拟主窗口那一层
        sp = _build("src.ui.settings_page", "SettingsPage")
        sp.setParent(host)
        box = sp._confirm_box("清空点赞计数", "将清空全部 3 项。")
        box.show()
        _app.processEvents()
        img = box.grab().toImage()
        tot = n = 0
        for y in range(0, img.height(), 4):
            for x in range(0, img.width(), 4):
                c = img.pixelColor(x, y)
                tot += c.red() + c.green() + c.blue()
                n += 1
        avg = tot / (n * 3.0)
        box.close()
        self.assertGreater(avg, 120,
                           "确认框整体偏黑（平均亮度 %.0f）—— 底色被继承的样式表弄没了" % avg)

    def test_没有记录时不弹确认框(self):
        """没东西可清就别弹框 —— 操作员会以为自己点错了。"""
        called = []
        self.sp._ask = lambda *a: called.append(1) or True
        self.sp._on_reset_likes()
        self.assertEqual(called, [], "没有记录还弹了确认框")
        self.assertIn("不用清", self.sp._like_status.text())

    def test_没接存档时点按钮不崩(self):
        self.sp._likes = None
        self.sp._on_reset_likes()
        self.sp.refresh_like_summary()


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

    def test_点赞记到当前对象头上(self):
        """端到端：真实 MainWindow 上，每个页面点赞都记到**该记的那个对象**上。

        ⚠ 桩测的是闸门逻辑（`test_gesture_gate.TestLikeCounting`）；这里验的是
        **接线** —— 真实页面上的 `_pi` / `_index` / `current_target()` 到底拿不拿得到。
        拿不到就退化成空串，那样**点赞静默不生效**（不报错、看着一切正常）。
        """
        from src import config
        from src.core.like_store import LikeStore
        from src.core.project_assets import slug_of
        from src.core.project_data import INHERITORS, PROJECTS
        from src.ui.main_window import IDX

        d = tempfile.mkdtemp(prefix="likes-e2e-")
        saved, self.win.likes = self.win.likes, LikeStore(os.path.join(d, "likes.json"))

        def like(label="like"):
            """走**完整的静态通道**喂一次点赞（要连喂两帧）"""
            self.win._cooldown_until = 0.0
            self.win._static_need_gap = False
            self.win._static_lg = None
            self.win._static_count = 0
            for _ in range(config.STATIC_CONSISTENCY):
                self.win._on_static({"label": label, "confidence": 0.99})

        try:
            # 首页第一排：选中第 3 个项目卡
            hp = self.win.pages["home"]
            self.win.stack.setCurrentIndex(IDX["home"])
            _app.processEvents()
            hp._move(2)
            _app.processEvents()
            like()
            self.assertEqual(self.win.likes.count("proj:" + slug_of(2)), 1)

            # 首页第二排：选中第 2 位传承人（⚠ 不是"项目 0"）
            hp._move(len(PROJECTS) + 1)
            _app.processEvents()
            like()
            self.assertEqual(self.win.likes.count("inh:" + INHERITORS[1]["name"]), 1,
                             "首页第二排的点赞记到项目上去了")

            # 详情页
            self.win._go_detail(3)
            _app.processEvents()
            like()
            self.assertEqual(self.win.likes.count("proj:" + slug_of(3)), 1)

            # 传承人页
            self.win._enter_inheritor(2)
            _app.processEvents()
            like()
            self.assertEqual(self.win.likes.count("inh:" + INHERITORS[2]["name"]), 1)

            # 设置页：没有可点赞的对象 → 什么都不记
            self.win.stack.setCurrentIndex(IDX["settings"])
            _app.processEvents()
            before = dict(self.win.likes.all_counts())
            like()
            self.assertEqual(self.win.likes.all_counts(), before, "设置页不该记点赞")
        finally:
            self.win.likes = saved
            shutil.rmtree(d, ignore_errors=True)

    def test_窗口能缩到默认尺寸以下(self):
        """⚠ **真实踩过**：设置页「手势说明」那一栏没套滚动区，里面那两张
        *按行数撑到固定高度*的表格，就把**主窗口的最小高度**顶到了 **943** ——
        比窗口自己的默认高度（800）还大。

        表现就是**"宽度能拉、高度拉不动"**，而且**连它自己的默认尺寸都到不了**。

        原理：`QStackedLayout` 取**所有页面**（含隐藏的）最小尺寸里**最大**的那个，
        所以随便哪一页里有个大的固定高度，都会一路顶到主窗口上 ——
        改单个页面的时候很难联想到它在卡窗口。
        """
        win = self.win
        old = win.size()
        try:
            win.resize(1280, 800)                       # MainWindow 里的默认尺寸
            _app.processEvents()
            self.assertEqual(win.height(), 800,
                             "连窗口自己的默认高度都到不了 —— 高度会调不动")
            win.resize(1280, 520)
            _app.processEvents()
            self.assertLess(win.height(), 800, "高度缩不动")
        finally:
            win.resize(old)
            _app.processEvents()

    def test_没有哪个页面把窗口高度顶得太高(self):
        """上一条只测了"窗口"，这条**点名是哪一页**干的。

        ⚠ 600 不是硬标准，是个**明确的红线**：改单个页面时很难联想到
        "我在卡整个窗口"，所以给出一个数 + 指出页面名，比"越小越好"有用。
        **别为了通过它去调这个数字** —— 该改的是那个把它顶上去的页面。
        """
        for name, p in self.win.pages.items():
            with self.subTest(页面=name):
                h = p.minimumSizeHint().height()
                self.assertLessEqual(h, 600,
                                     f"{name} 页的最小高度是 {h}，会把窗口高度顶住")

    def test_设置页与主窗口用的是同一个点赞存档(self):
        """⚠ 设置页自己持有一份引用（`set_like_store`）。主窗口忘了给的话，
        "清空点赞计数"按钮会**点了没反应**，而且不报错。

        （这条不能靠下面那条端到端用例守 —— 那条为了让用例可重跑，
        自己会把临时存档再接一次，正好把"主窗口根本没接"这件事盖住。
        变异验证抓到过。）
        """
        self.assertIs(self.win.pages["settings"]._likes, self.win.likes,
                      "设置页拿到的不是主窗口那个点赞存档")

    def test_首页角标取的是主窗口那个点赞存档(self):
        """同理：首页是"拉模式"。来源函数没接上、或者接了别的存档，
        角标就永远是 0 —— 不报错，只是**功能静默失效**。

        ⚠ 用桩、**不往真存档里写** —— 那是展台上的运行数据，测试不许碰。
        """
        class _Stub:
            def count(self, key):
                return 42

        self.assertIsNotNone(self.win.pages["home"]._like_source,
                             "首页根本没接上点赞来源")
        saved, self.win.likes = self.win.likes, _Stub()
        try:
            self.assertEqual(self.win._like_count_for("project", 0), 42,
                             "角标读的不是主窗口那个点赞存档")
        finally:
            self.win.likes = saved

    def test_清空点赞会把首页角标也清掉(self):
        """端到端：清空之后**屏幕上**不能还留着已经删掉的数字。

        ⚠ 主窗口持有 `likes`，设置页也单独持有一份（`set_like_store`）——
        两处指的是同一个对象，**换成临时存档时必须两处一起换**，
        只换一处的话这条用例就在测另一个存档了。
        """
        from src import config
        from src.core.like_store import LikeStore
        from src.ui.main_window import IDX

        d = tempfile.mkdtemp(prefix="likes-reset-e2e-")
        store = LikeStore(os.path.join(d, "likes.json"))
        saved_store = self.win.likes
        saved_sp = self.win.pages["settings"]._likes
        try:
            self.win.likes = store
            self.win.pages["settings"].set_like_store(store)

            # 先在首页第 1 张卡上点个赞
            self.win.stack.setCurrentIndex(IDX["home"])
            _app.processEvents()
            hp = self.win.pages["home"]
            hp._move(0)
            _app.processEvents()
            self.win._cooldown_until = 0.0
            self.win._static_need_gap = False
            self.win._static_lg = None
            self.win._static_count = 0
            for _ in range(config.STATIC_CONSISTENCY):
                self.win._on_static({"label": "like", "confidence": 0.99})
            self.assertGreater(hp._cards[0].like_count(), 0, "点赞没记上")

            # 从设置页清空
            sp = self.win.pages["settings"]
            sp._ask = lambda *a: True
            sp._on_reset_likes()

            self.assertEqual(store.all_counts(), {})
            self.assertEqual(hp._cards[0].like_count(), 0,
                             "存档清了，首页角标还留着旧数字")
        finally:
            self.win.likes = saved_store
            self.win.pages["settings"].set_like_store(saved_sp)
            shutil.rmtree(d, ignore_errors=True)

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
