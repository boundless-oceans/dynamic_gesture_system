"""传承人风采页"""

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from src.ui.base_page import BasePage


class InheritorPage(BasePage):
    go_home = Signal()

    def __init__(self):
        super().__init__()
        self._index = 0
        self._total = 6
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("传承人风采")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 42, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title)

        top_row = QHBoxLayout()
        top_row.addStretch()
        btn_up = QPushButton("\u2191")
        btn_up.setFixedSize(60, 60)
        btn_up.setFont(QFont("Arial", 24))
        btn_up.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:30px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_up.clicked.connect(self._prev)
        top_row.addWidget(btn_up)
        layout.addLayout(top_row)

        self._content = QLabel(f"传承人 {self._index + 1} / {self._total}")
        self._content.setAlignment(Qt.AlignCenter)
        self._content.setFont(QFont("STKaiti", 24))
        self._content.setStyleSheet("background: rgba(255,255,255,0.35); border-radius: 16px;")
        layout.addWidget(self._content, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_down = QPushButton("\u2193")
        btn_down.setFixedSize(60, 60)
        btn_down.setFont(QFont("Arial", 24))
        btn_down.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:30px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_down.clicked.connect(self._next)
        bottom_row.addWidget(btn_down)
        bottom_row.addSpacing(10)
        btn_back = QPushButton("\u21A9", self)
        btn_back.setFixedSize(60, 60)
        btn_back.setFont(QFont("Arial", 24))
        btn_back.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:30px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_back.clicked.connect(self.go_home.emit)
        bottom_row.addWidget(btn_back)
        layout.addLayout(bottom_row)

    def _prev(self):
        self._index = (self._index - 1) % self._total
        self._update()

    def _next(self):
        self._index = (self._index + 1) % self._total
        self._update()

    def _update(self):
        self._content.setText(f"传承人 {self._index + 1} / {self._total}")
