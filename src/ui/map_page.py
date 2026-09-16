"""非遗地图页"""
import os
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QHBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont
from src.ui.base_page import BasePage

_BTN_SEL="QPushButton{background:rgba(255,255,255,0.95);border:3px solid #ffb300;border-radius:25px;}QPushButton:hover{background:#fff;}"


class MapPage(BasePage):
    go_home = Signal()
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.web = QWebEngineView()
        self.web.settings().setAttribute(self.web.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True)
        html = os.path.join(os.path.dirname(__file__), "../../pages/map.html")
        self.web.load(QUrl.fromLocalFile(os.path.abspath(html)))
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
