"""首页：非遗项目轮播展示"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QLinearGradient, QColor


ITEMS = ["葫芦雕刻", "刘铭传故事", "包公故事", "庐剧", "火笔画", "吴山铁字"]

_FROSTED = "QFrame { background: rgba(255,255,255,0.45); border: 1px solid rgba(255,255,255,0.7); border-radius: 16px; } QFrame:hover { background: rgba(255,255,255,0.75); border: 2px solid #ff9900; }"


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
        layout.addWidget(img)
        name_label = QLabel(name)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        name_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(name_label)

    def mousePressEvent(self, event):
        self.clicked.emit(self.index)

    def mouseDoubleClickEvent(self, event):
        self.double_clicked.emit(self.index)

    def set_selected(self, selected: bool):
        if selected:
            self.setFixedSize(175, 300)
            self.setStyleSheet("QFrame { background: rgba(255,255,255,0.8); border: 3px solid #ff7700; border-radius: 18px; }")
        else:
            self.setFixedSize(160, 280)
            self.setStyleSheet(_FROSTED)


class HomePage(QWidget):
    item_selected = Signal(int)

    def __init__(self):
        super().__init__()
        self._current = 0
        self._cards: list[_ItemCard] = []
        self._setup_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(91, 167, 209))
        painter.fillRect(self.rect(), gradient)

    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("庐州非遗")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 48, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title, stretch=1)

        carousel_layout = QHBoxLayout()
        carousel_layout.setAlignment(Qt.AlignCenter)
        carousel_layout.setSpacing(20)

        btn_left = QPushButton("<")
        btn_left.setFixedSize(50, 50)
        btn_left.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        btn_left.setStyleSheet("QPushButton { background: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.6); border-radius: 25px; } QPushButton:hover { background: rgba(255,255,255,0.9); }")
        btn_left.clicked.connect(self._prev)
        carousel_layout.addWidget(btn_left)

        for i, name in enumerate(ITEMS):
            card = _ItemCard(i, name)
            card.clicked.connect(self._on_select)
            card.double_clicked.connect(self._on_double)
            self._cards.append(card)
            carousel_layout.addWidget(card)

        btn_right = QPushButton(">")
        btn_right.setFixedSize(50, 50)
        btn_right.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        btn_right.setStyleSheet("QPushButton { background: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.6); border-radius: 25px; } QPushButton:hover { background: rgba(255,255,255,0.9); }")
        btn_right.clicked.connect(self._next)
        carousel_layout.addWidget(btn_right)

        layout.addLayout(carousel_layout, stretch=3)
        self._cards[0].set_selected(True)

    def _prev(self):
        self._current = (self._current - 1) % len(ITEMS)
        self._update_selection()

    def _next(self):
        self._current = (self._current + 1) % len(ITEMS)
        self._update_selection()

    def _on_select(self, index: int):
        self._current = index
        self._update_selection()

    def _on_double(self, index: int):
        self._current = index
        self._update_selection()
        self.item_selected.emit(self._current)

    def _update_selection(self):
        for i, card in enumerate(self._cards):
            card.set_selected(i == self._current)

    def current_item(self) -> str:
        return ITEMS[self._current]
