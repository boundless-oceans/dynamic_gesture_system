"""非遗地图页"""
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QHBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from src.ui.base_page import BasePage
from src import paths
from src.ui.web_util import LogPage, local_url

_BTN_SEL="QPushButton{background:rgba(255,255,255,0.95);border:3px solid #ffb300;border-radius:25px;}QPushButton:hover{background:#fff;}"


class MapPage(BasePage):
    go_home = Signal()
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web = QWebEngineView()
        # 装 JS 控制台转发：不装的话地图页的 console 与 JS 报错会被**静默丢弃**，
        # 而地图是唯一依赖网络的页面，断网/被拦时表现就是一张空白图、零条诊断
        self.web.setPage(LogPage(QWebEngineProfile.defaultProfile(), self.web))
        self.web.settings().setAttribute(self.web.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True)
        html = paths.resource_path("pages", "map.html")
        url = local_url(html)           # 带版本号，改完 HTML 不必清缓存
        print(f"[Map] loading {url.toString()}", flush=True)
        self.web.load(url)
        layout.addWidget(self.web)
        bl = QHBoxLayout(); bl.addStretch()
        btn = QPushButton("\u21A9"); btn.setFixedSize(50, 50)
        btn.setFont(QFont("Arial", 20))
        btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn.clicked.connect(self.go_home.emit)
        bl.addWidget(btn); layout.addLayout(bl)

        # 天然选中"返回"按钮（本页唯一可选项）
        self._btn_back = btn
        self._btn_back.setStyleSheet(_BTN_SEL)

    def select_prev(self):
        pass

    def select_next(self):
        pass

    def activate_selected(self):
        self.go_home.emit()

    def zoom_in(self):
        self.web.page().runJavaScript("zoomIn()")

    def zoom_out(self):
        self.web.page().runJavaScript("zoomOut()")

    def pan_up(self):
        self.web.page().runJavaScript("panUp()")

    def pan_down(self):
        self.web.page().runJavaScript("panDown()")

    def pan_left(self):
        self.web.page().runJavaScript("panLeft()")

    def pan_right(self):
        self.web.page().runJavaScript("panRight()")
