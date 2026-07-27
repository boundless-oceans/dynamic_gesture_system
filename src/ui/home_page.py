"""首页：非遗项目轮播展示"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QLinearGradient, QColor


# 6 个非遗项目
ITEMS = ["葫芦雕刻", "刘铭传故事", "包公故事", "庐剧", "火笔画", "吴山铁字"]


class _ItemCard(QFrame):
    """单个非遗项目卡片"""

    clicked = Signal(int)       # 单击 → 选中
    double_clicked = Signal(int)  # 双击 → 进入

    def __init__(self, index: int, name: str):
        super().__init__()
        self.index = index
        self._name = name
        self._selected = False

        self.setFixedSize(160, 280)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background: rgba(255,255,255,0.9);
                border: 2px solid #ccc;
                border-radius: 12px;
            }
            QFrame:hover {
                border: 2px solid #ff9900;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # 图片占位区
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setFixedHeight(200)
        self.image_label.setStyleSheet("""
            background: #e8e8e8;
            border-radius: 8px;
        """)
        layout.addWidget(self.image_label)

        # 名称
        self.name_label = QLabel(name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        self.name_label.setStyleSheet("background: transparent; border: none;")
        layout.addWidget(self.name_label)

    def mousePressEvent(self, event):
        """单击 → 选中"""
        self.clicked.emit(self.index)

    def mouseDoubleClickEvent(self, event):
        """双击 → 进入"""
        self.double_clicked.emit(self.index)

    def set_selected(self, selected: bool):
        self._selected = selected
        if selected:
            self.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.95);
                    border: 3px solid #ff7700;
                    border-radius: 14px;
                }
            """)
            self.setFixedSize(175, 300)
        else:
            self.setFixedSize(160, 280)
            self.setStyleSheet("""
                QFrame {
                    background: rgba(255,255,255,0.9);
                    border: 2px solid #ccc;
                    border-radius: 12px;
                }
                QFrame:hover {
                    border: 2px solid #ff9900;
                }
            """)


class HomePage(QWidget):
    """首页"""

    # 用户选中某个项目（index）
    item_selected = Signal(int)
    # 切换摄像头
    camera_toggle = Signal()

    def __init__(self):
        super().__init__()
        self._current = 0
        self._cards: list[_ItemCard] = []

        self._setup_ui()

    def paintEvent(self, event):
        """绘制白→蓝渐变背景"""
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(91, 167, 209))
        painter.fillRect(self.rect(), gradient)

    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ---- 顶部标题 ----
        self.title = QLabel("庐州非遗")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setFont(QFont("STKaiti", 48, QFont.Bold))
        self.title.setStyleSheet("background: transparent;")
        layout.addWidget(self.title, stretch=1)

        # ---- 中间按钮组 ----
        carousel_layout = QHBoxLayout()
        carousel_layout.setAlignment(Qt.AlignCenter)
        carousel_layout.setSpacing(20)

        # 左箭头
        self.btn_left = QPushButton("<")
        self.btn_left.setFixedSize(50, 50)
        self.btn_left.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        self.btn_left.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.8);
                border: none;
                border-radius: 25px;
            }
            QPushButton:hover { background: rgba(255,255,255,1); }
        """)
        self.btn_left.clicked.connect(self._prev)
        carousel_layout.addWidget(self.btn_left)

        # 6 个卡片
        for i, name in enumerate(ITEMS):
            card = _ItemCard(i, name)
            card.clicked.connect(self._on_select)          # 单击 → 选中
            card.double_clicked.connect(self._on_double)   # 双击 → 进入
            self._cards.append(card)
            carousel_layout.addWidget(card)

        # 右箭头
        self.btn_right = QPushButton(">")
        self.btn_right.setFixedSize(50, 50)
        self.btn_right.setFont(QFont("Microsoft YaHei", 20, QFont.Bold))
        self.btn_right.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.8);
                border: none;
                border-radius: 25px;
            }
            QPushButton:hover { background: rgba(255,255,255,1); }
        """)
        self.btn_right.clicked.connect(self._next)
        carousel_layout.addWidget(self.btn_right)

        layout.addLayout(carousel_layout, stretch=3)

        # ---- 关闭摄像头按钮 ----
        self.btn_camera = QPushButton("关闭摄像头")
        self.btn_camera.setFont(QFont("Microsoft YaHei", 10))
        self.btn_camera.setFixedSize(120, 36)
        self.btn_camera.setStyleSheet("""
            QPushButton {
                background: rgba(255,255,255,0.7);
                border: 1px solid #aaa;
                border-radius: 6px;
            }
            QPushButton:hover { background: rgba(255,255,255,1); }
        """)
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.addWidget(self.btn_camera)
        layout.addLayout(btn_layout)

        # 初始化选中第一个
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
        """双击 → 触发进入"""
        self._current = index
        self._update_selection()
        self.item_selected.emit(self._current)

    def _update_selection(self):
        for i, card in enumerate(self._cards):
            card.set_selected(i == self._current)

    def current_item(self) -> str:
        return ITEMS[self._current]
