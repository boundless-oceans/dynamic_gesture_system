"""3D 交互查看页"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QFont


class ViewerPage(QWidget):
    """Three.js 3D 模型交互查看"""

    go_home = Signal()

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web = QWebEngineView()
        html_path = os.path.join(os.path.dirname(__file__), "../../pages/viewer.html")
        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))
        layout.addWidget(self.web)

        # 右下角返回按钮（覆盖在网页上）
        self.btn_back = QPushButton("\u21A9", self)
        self.btn_back.setFixedSize(60, 60)
        self.btn_back.setFont(QFont("Arial", 24))
        self.btn_back.setStyleSheet("""
            QPushButton {
                background: white; border: none; border-radius: 30px;
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
            QPushButton:hover { background: #f0f0f0; }
        """)
        self.btn_back.clicked.connect(self.go_home.emit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.btn_back.move(self.width() - 80, self.height() - 80)

    def zoom_in(self):
        self.web.page().runJavaScript("zoomIn()")

    def zoom_out(self):
        self.web.page().runJavaScript("zoomOut()")

    def circle(self):
        self.web.page().runJavaScript("circle()")
