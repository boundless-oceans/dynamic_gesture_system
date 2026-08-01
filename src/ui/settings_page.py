"""设置页：手势对照表"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QLinearGradient, QColor


class SettingsPage(QWidget):
    """手势操作说明"""

    go_home = Signal()

    def __init__(self):
        super().__init__()
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
        layout.setContentsMargins(40, 40, 40, 40)

        title = QLabel("手势操作说明")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 36, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title)

        layout.addSpacing(20)

        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["动态手势", "首页", "详情页", "3D 查看"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setFont(QFont("Microsoft YaHei", 12))

        rows = [
            ["swipe_left",   "\u2190 上一项",     "",                ""],
            ["swipe_right",  "\u2192 下一项",     "",                ""],
            ["swipe_up",     "",                 "\u2191 向上滚动",  ""],
            ["swipe_down",   "",                 "\u2193 向下滚动",  ""],
            ["click",        "\u2714 进入详情",  "",                ""],
            ["palm",         "\u21A9 回到首页",   "\u21A9 回到首页", "\u21A9 回到首页"],
            ["zoom_in",      "",                 "",                "\u2795 放大"],
            ["zoom_out",     "",                 "",                "\u2796 缩小"],
            ["circle",       "",                 "",                "\u21BB 旋转"],
        ]
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, cell in enumerate(row):
                item = QTableWidgetItem(cell)
                item.setTextAlignment(Qt.AlignCenter)
                if j == 0:
                    item.setFont(QFont("Consolas", 12, QFont.Bold))
                table.setItem(i, j, item)

        table.setStyleSheet("""
            QTableWidget {
                background: rgba(255,255,255,0.5);
                border-radius: 10px; gridline-color: #ddd;
            }
            QHeaderView::section {
                background: rgba(91,167,209,0.3);
                font-weight: bold; padding: 8px;
            }
        """)
        layout.addWidget(table)

        nav = QHBoxLayout()
        nav.setAlignment(Qt.AlignCenter)
        btn_home = QPushButton("返回首页")
        btn_home.setFixedSize(140, 44)
        btn_home.setFont(QFont("Microsoft YaHei", 13))
        btn_home.setStyleSheet("QPushButton { background: rgba(255,255,255,0.8); border: 1px solid #aaa; border-radius: 8px; } QPushButton:hover { background: rgba(255,255,255,1); }")
        btn_home.clicked.connect(self.go_home.emit)
        nav.addWidget(btn_home)
        layout.addLayout(nav)

        layout.addSpacing(10)

        tip = QLabel("提示：鼠标点击按钮作为兜底操作，摄像头关闭时仍可正常使用")
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("Microsoft YaHei", 11))
        tip.setStyleSheet("background: transparent; color: #555;")
        layout.addWidget(tip)
