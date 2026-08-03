"""非遗地图页"""
import os
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QHBoxLayout
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont
from src.ui.base_page import BasePage


class MapPage(BasePage):
    go_home = Signal()
    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        web = QWebEngineView()
        web.settings().setAttribute(web.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True)
        html = os.path.join(os.path.dirname(__file__), "../../pages/map.html")
        web.load(QUrl.fromLocalFile(os.path.abspath(html)))
        layout.addWidget(web)
        bl = QHBoxLayout(); bl.addStretch()
        btn = QPushButton("\u21A9"); btn.setFixedSize(50, 50)
        btn.setFont(QFont("Arial", 20))
        btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn.clicked.connect(self.go_home.emit)
        btn.clicked.connect(self.go_home.emit)
        bl.addWidget(btn); layout.addLayout(bl)
