"""首页"""

import os

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor, QPixmap
from PySide6.QtWidgets import QGraphicsDropShadowEffect

from src.ui.base_page import BasePage

from src.core.project_data import get_names as _get_names
from src.core import project_assets as _PA
ITEMS = _get_names()
_FROSTED = "QFrame { background: rgba(255,255,255,0.25); border: 1px solid rgba(255,255,255,0.5); border-radius: 16px; } QFrame:hover { background: rgba(255,255,255,0.55); border: 2px solid #ff9900; }"


class _ItemCard(QFrame):
    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(self, index: int, name: str):
        super().__init__()
        self.index = index
        self.setFixedSize(160, 280)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(_FROSTED)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        img = QLabel()
        img.setAlignment(Qt.AlignCenter)
        img.setFixedHeight(200)
        img.setStyleSheet("background: rgba(255,255,255,0.3); border-radius: 10px;")
        self._img = img
        self._load_image(index)
        layout.addWidget(img)
        nl = QLabel(name)
        nl.setAlignment(Qt.AlignCenter)
        nl.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        nl.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(nl)

    def _load_image(self, index: int):
        """加载项目卡片图 assets/images/<slug>/thumb.jpg"""
        path = _PA.thumb_path(index)
        if path and os.path.exists(path):
            pm = QPixmap(path).scaled(144, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self._img.setPixmap(pm)

    def mousePressEvent(self, e): self.clicked.emit(self.index)
    def mouseDoubleClickEvent(self, e): self.double_clicked.emit(self.index)

    def set_selected(self, s: bool):
        if s:
            self.setFixedSize(175, 300)
            self.setStyleSheet("QFrame { background: rgba(255,255,255,0.5); border: 3px solid #ff7700; border-radius: 18px; }")
        else:
            self.setFixedSize(160, 280)
            self.setStyleSheet(_FROSTED)


class HomePage(BasePage):
    item_selected = Signal(int)
    go_inheritor = Signal()
    go_map = Signal()

    def __init__(self):
        super().__init__()
        self._current = 0
        self._cards: list[_ItemCard] = []
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("庐州非遗")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 48, QFont.Bold))
        title.setStyleSheet("background: transparent; color: #1a3a5c;")
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(20)
        glow.setColor(QColor(200, 160, 60, 200))
        glow.setOffset(0, 0)
        title.setGraphicsEffect(glow)
        layout.addWidget(title, stretch=1)
        cl = QHBoxLayout()
        cl.setAlignment(Qt.AlignCenter)
        cl.setSpacing(20)
        self.btn_left = QPushButton("<"); self.btn_left.setFixedSize(50, 50); self.btn_left.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        self.btn_left.setStyleSheet("QPushButton { background: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.6); border-radius: 25px; } QPushButton:hover { background: rgba(255,255,255,0.9); }")
        self.btn_left.clicked.connect(self._prev); cl.addWidget(self.btn_left)
        for i, name in enumerate(ITEMS):
            c = _ItemCard(i, name); c.clicked.connect(self._on_select); c.double_clicked.connect(self._on_double)
            self._cards.append(c); cl.addWidget(c)
        br = QPushButton(">"); br.setFixedSize(50, 50); br.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        br.setStyleSheet("QPushButton { background: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.6); border-radius: 25px; } QPushButton:hover { background: rgba(255,255,255,0.9); }")
        br.clicked.connect(self._next); cl.addWidget(br)
        layout.addLayout(cl, stretch=3)
        self._cards[0].set_selected(True)

        seal=QLabel("非遗\n之宝",self)
        seal.setFixedSize(128,128); seal.setAlignment(Qt.AlignCenter)
        seal.setFont(QFont("STKaiti",26,QFont.Bold))
        seal.setStyleSheet("color:white;background:rgba(180,40,40,0.65);border:3px solid rgba(140,30,30,0.6);border-radius:8px;")
        seal.move(24,24)

    def _prev(self):
        # 向左：选中左移一格；已在最左则进入高德地图
        if self._current > 0:
            self._current -= 1; self._update()
        else:
            self.go_map.emit()

    def _next(self):
        # 向右：选中右移一格；已在最右则进入非遗传承人
        if self._current < len(ITEMS) - 1:
            self._current += 1; self._update()
        else:
            self.go_inheritor.emit()

    def current_index(self) -> int:
        return self._current
    def _on_select(self, i: int): self._current = i; self._update()
    def _on_double(self, i: int): self._current = i; self._update(); self.item_selected.emit(self._current)
    def _update(self):
        for i, c in enumerate(self._cards): c.set_selected(i == self._current)
    def current_item(self) -> str: return ITEMS[self._current]
