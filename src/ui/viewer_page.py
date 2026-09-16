"""3D 交互查看页"""

import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QFont

_BACK_SEL = "QPushButton{background:rgba(255,255,255,0.95);border:3px solid #ffb300;border-radius:30px;}QPushButton:hover{background:#fff;}"


class ViewerPage(QWidget):
    """Three.js 3D 模型交互查看"""

    go_home = Signal()

    def __init__(self):
        super().__init__()
        self._slug = None            # 当前加载的模型 slug
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.web = QWebEngineView()
        html_path = os.path.join(os.path.dirname(__file__), "../../pages/viewer.html")
        self.web.load(QUrl.fromLocalFile(os.path.abspath(html_path)))
        self.web.loadFinished.connect(self._on_loaded)
        layout.addWidget(self.web)

        # 右下角返回按钮（覆盖在网页上）
        self.btn_back = QPushButton("\u21A9", self)
        self.btn_back.setFixedSize(60, 60)
        self.btn_back.setFont(QFont("Arial", 24))
        # 3D \u9875\uFF1A\u8FD4\u56DE\u952E\u9ED8\u8BA4\u9009\u4E2D\uFF08\u91D1\u8FB9\uFF09\uFF0C\u70B9\u51FB/\u786E\u8BA4=\u8FD4\u56DE
        self.btn_back.setStyleSheet(_BACK_SEL)
        self.btn_back.clicked.connect(self.go_home.emit)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.btn_back.move(self.width() - 80, self.height() - 80)

    def _on_loaded(self, ok):
        if ok:
            self._apply_model()

    def _apply_model(self):
        if self._slug:
            self.web.page().runJavaScript("loadModel('%s')" % self._slug)

    def load_model(self, slug: str):
        """按项目 slug 加载 ../assets/models/<slug>.glb"""
        if not slug:
            return
        self._slug = slug
        self._apply_model()

    def zoom_in(self):
        self.web.page().runJavaScript("zoomIn()")

    def zoom_out(self):
        self.web.page().runJavaScript("zoomOut()")

    def circle(self):
        self.web.page().runJavaScript("circle()")

    # 唯一可选项=返回键（默认选中）
    def select_prev(self):
        pass

    def select_next(self):
        pass

    def activate_selected(self):
        self.go_home.emit()
