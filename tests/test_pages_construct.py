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

from PySide6.QtWidgets import QApplication

_app = None

PAGES = [
    ("src.ui.home_page", "HomePage"),
    ("src.ui.detail_page", "DetailPage"),
    ("src.ui.settings_page", "SettingsPage"),
    ("src.ui.inheritor_page", "InheritorPage"),
    ("src.ui.map_page", "MapPage"),
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

    def test_主窗口可构造且权重状态正常(self):
        from src.ui.main_window import MainWindow
        win = MainWindow()
        _app.processEvents()
        self.assertEqual(win.recognizer.status, "ok",
                         f"权重状态异常: {win.recognizer.status} {win.recognizer.status_detail}")
        win.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
