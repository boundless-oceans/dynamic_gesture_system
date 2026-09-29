"""网页页面的两个共用工具：JS 控制台转发、本地 URL 防缓存

守的是两件**会静默失效**的事：

  * **JS 输出被丢掉** —— 默认的 `QWebEnginePage` 会把 `console.log` 和未捕获的
    JS 异常直接扔了。3D 页和地图页都靠 JS 驱动，页面白了你却什么都看不到。
    地图页尤其要紧：它是**唯一依赖网络**的页面（高德瓦片），断网时的表现
    就是一张空白图加**零条诊断**。（实际踩到过：地图页一直没装转发。）

  * **改了 HTML 不生效** —— QtWebEngine 缓存本地页面，改完重启还是旧的。
    挂 mtime 当查询串绕开。（`viewer_page` 早就做了，`map_page` 漏着，
    同一个坑踩了两次。）
"""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")   # 无显示器也能跑

from PySide6.QtWidgets import QApplication

from src.ui.web_util import LogPage, local_url

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_app = None


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication(sys.argv)


class TestLocalUrl(unittest.TestCase):

    def test_指向该文件的绝对路径(self):
        p = os.path.join(REPO, "pages", "map.html")
        url = local_url(p)
        self.assertTrue(url.isLocalFile())
        self.assertEqual(os.path.normcase(os.path.abspath(url.toLocalFile())),
                         os.path.normcase(p))

    def test_带上版本号(self):
        """没有它 WebEngine 会拿缓存里的旧页面，改了 HTML 也不生效"""
        p = os.path.join(REPO, "pages", "map.html")
        self.assertIn("v=", local_url(p).query())

    def test_版本号跟着文件修改时间走(self):
        """mtime 一变版本号就得变，否则防缓存等于没防"""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.html")
            with open(p, "w", encoding="utf-8") as f:
                f.write("<html></html>")
            first = local_url(p).query()
            os.utime(p, (0, 0))          # 把 mtime 改到很久以前
            self.assertNotEqual(first, local_url(p).query())

    def test_文件不存在也不抛异常(self):
        """构建期/部署期文件可能还没到位，不能因此把页面构造搞崩"""
        url = local_url(os.path.join(REPO, "pages", "根本没有这个文件.html"))
        self.assertTrue(url.isLocalFile())


class TestPagesUseTheTools(unittest.TestCase):
    """防回归：两个网页页面都必须装上转发、都用带版本号的 URL。

    地图页曾经直接用裸的 `QWebEngineView()`，JS 报错全被吞掉。
    """

    PAGES = [("src.ui.map_page", "MapPage"),
             ("src.ui.viewer_page", "ViewerPage")]

    def _build(self, module, cls):
        mod = __import__(module, fromlist=[cls])
        w = getattr(mod, cls)()
        _app.processEvents()
        return w

    def test_都装了_JS_控制台转发(self):
        for module, cls in self.PAGES:
            with self.subTest(page=cls):
                w = self._build(module, cls)
                self.assertIsInstance(
                    w.web.page(), LogPage,
                    "%s 没装 LogPage —— 网页里的 console 与 JS 报错会被静默丢弃" % cls)

    def test_加载的_URL_都带版本号(self):
        """从页面自己打印的 `[Xxx] loading ...` 行里读。

        不查 `web.url()` —— 那是**异步提交后**的 URL，`load()` 刚调完还是空的。
        而且这么查正好测的是"现场日志里能看到的东西"。
        """
        for module, cls in self.PAGES:
            with self.subTest(page=cls):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    self._build(module, cls)
                lines = [l for l in buf.getvalue().splitlines() if "loading" in l]
                self.assertTrue(lines, "%s 没有打印加载的 URL" % cls)
                self.assertIn("v=", lines[-1],
                              "%s 的 URL 没版本号 —— 改完 HTML 会被缓存挡住" % cls)
                self.assertIn("map.html" if cls == "MapPage" else "viewer.html",
                              lines[-1], "%s 加载的不是预期的文件" % cls)


if __name__ == "__main__":
    unittest.main()
