"""QWebEngineView 的两个共用小工具（3D 页与地图页都用）

**为什么需要**

1. **把网页里的 console 与报错转到日志**

   默认的 `QWebEnginePage` 会把 `console.log` 和未捕获的 JS 异常**直接丢掉**。
   3D 页和地图页都靠 JS 驱动，页面白了你却什么都看不到。

   尤其地图页是**唯一依赖网络**的页面（高德瓦片）：在文化馆断网或被拦时，
   表现是一张空白地图加**零条诊断**。这正是日志系统该兜住的情形。

2. **本地 HTML 的 URL 带版本号**

   QtWebEngine 会缓存本地页面 —— 改完 HTML 重启还是旧的那一份。
   把文件 mtime 挂成查询串就能绕开。
   （`viewer_page` 早就这么做了，而 `map_page` 一直漏着，属于同一个坑踩两次。）
"""

import os

from PySide6.QtCore import QUrl
from PySide6.QtWebEngineCore import QWebEnginePage


class LogPage(QWebEnginePage):
    """把网页 console 与 JS 报错转发到 print（进而进日志文件）"""

    def javaScriptConsoleMessage(self, level, msg, line, src):
        print(f"[JS] {msg}  ({src}:{line})", flush=True)


def local_url(path: str) -> QUrl:
    """本地 HTML 的 URL，带 `?v=<mtime>` 避免 WebEngine 拿缓存里的旧页面"""
    url = QUrl.fromLocalFile(os.path.abspath(path))
    try:
        url.setQuery("v=%d" % int(os.path.getmtime(path)))
    except OSError:
        pass
    return url
