"""应用图标：文件有效、尺寸齐、Qt 真能加载出来

守的是三件会**静默失效**的事：

  * 图标文件被误删 / 忘了提交 —— 运行起来任务栏就是默认的 Qt 图标，不报错
  * 重新生成时丢了几个尺寸 —— 高 DPI 屏或资源管理器大图标视图下会糊
  * 生成脚本的尺寸表和文件对不上 —— 下次 `make_icon.py` 一跑就把文件改回去

"窗口图标设没设"这一条本机测不到（那是 `main.py` 的 `__main__` 块），
靠离屏假 exec 跑一遍真入口来验，见仓库工作记录。
"""
import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # 无显示器也能跑

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from src import paths

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICO = os.path.join(REPO_ROOT, "assets", "app_icon.ico")

_app = None


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication(sys.argv)


def _icon_sizes() -> set:
    """文件里实际含有的尺寸集合"""
    from PIL import Image
    with Image.open(ICO) as im:
        return set(im.info.get("sizes", []))


def _script_sizes() -> list:
    """tools/make_icon.py 里声明的尺寸表（只取常量，不执行 main）"""
    spec = importlib.util.spec_from_file_location(
        "make_icon", os.path.join(REPO_ROOT, "tools", "make_icon.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SIZES


class TestIconFile(unittest.TestCase):

    def test_文件在_paths_解析得到的位置(self):
        """路径必须走 paths —— 打包后 __file__ 指向只读的 _internal/"""
        self.assertEqual(os.path.abspath(ICO),
                         paths.resource_path("assets", "app_icon.ico"))
        self.assertTrue(os.path.exists(ICO), "图标文件不在，任务栏会退回默认图标")

    def test_尺寸与生成脚本一致(self):
        """对不上就说明有人只改了一边；下次跑 make_icon.py 会把文件覆盖回去"""
        self.assertEqual(_icon_sizes(), {(n, n) for n in _script_sizes()})

    def test_尺寸覆盖到_16_和_256_两端(self):
        """16px 是资源管理器小图标视图，256px 是高 DPI 大图标；
        少了任一端都会有场景退化成缩放后的糊图"""
        sizes = _icon_sizes()
        self.assertIn((16, 16), sizes)
        self.assertIn((256, 256), sizes)

    def test_脚本的尺寸表是降序且不重复(self):
        sizes = _script_sizes()
        self.assertEqual(sizes, sorted(set(sizes), reverse=True))


class TestQtCanLoad(unittest.TestCase):

    def test_Qt_读得出图标不是空的(self):
        icon = QIcon(ICO)
        self.assertFalse(icon.isNull(), "Qt 读不出这个 ico —— 窗口图标会是空白")

    def test_每个尺寸都能取出位图(self):
        """availableSizes 少一档，对应场景下 Qt 就得缩放，会糊"""
        icon = QIcon(ICO)
        got = {(s.width(), s.height()) for s in icon.availableSizes()}
        self.assertEqual(got, {(n, n) for n in _script_sizes()})

    def test_常用尺寸能取出非空位图(self):
        icon = QIcon(ICO)
        for n in (16, 32, 48, 256):
            with self.subTest(size=n):
                pm = icon.pixmap(n, n)
                self.assertFalse(pm.isNull(), f"{n}px 取不出位图")


if __name__ == "__main__":
    unittest.main()
