"""3D 交互查看页"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, Signal


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

    def zoom_in(self):
        self.web.page().runJavaScript("zoomIn()")

    def zoom_out(self):
        self.web.page().runJavaScript("zoomOut()")

    def circle(self):
        self.web.page().runJavaScript("circle()")
