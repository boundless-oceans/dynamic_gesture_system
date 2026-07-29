"""详情页：非遗项目介绍"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget,
    QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QLinearGradient, QColor


class DetailPage(QWidget):
    """详情页：含主视图和非遗详情子视图"""

    go_home = Signal()
    go_viewer = Signal()

    def reset_to_main(self):
        """回到主视图（从其他子视图返回时调用）"""
        self.stack.setCurrentIndex(0)

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
        layout.setContentsMargins(20, 20, 20, 20)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        self.main_view = self._create_main_view()
        self.detail_view = self._create_detail_view()
        self.stack.addWidget(self.main_view)
        self.stack.addWidget(self.detail_view)
        layout.addWidget(self.stack)

    # ---- 主视图：3D 占位 + 导航按钮 ----
    def _create_main_view(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)

        title = QLabel("包公故事")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 42, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title, stretch=1)

        placeholder = QLabel("3D 模型预览区")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("background: rgba(255,255,255,0.3); border: 2px dashed #aaa; border-radius: 16px; font-size: 20px; color: #666;")
        layout.addWidget(placeholder, stretch=4)

        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignCenter)
        btn_layout.setSpacing(30)
        self.btn_home = QPushButton("返回主页")
        self.btn_detail = QPushButton("非遗详情")
        self.btn_viewer = QPushButton("交互展示")
        for btn in [self.btn_home, self.btn_detail, self.btn_viewer]:
            btn.setFixedSize(140, 50)
            btn.setFont(QFont("Microsoft YaHei", 14))
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.8); border: 1px solid #aaa; border-radius: 10px; } QPushButton:hover { background: rgba(255,255,255,1); }")
            btn_layout.addWidget(btn)
        self.btn_home.clicked.connect(self.go_home.emit)
        self.btn_detail.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        self.btn_viewer.clicked.connect(self.go_viewer.emit)
        layout.addLayout(btn_layout, stretch=1)
        return w

    # ---- 非遗详情子视图：文字 + 视频 + 图片 ----
    def _create_detail_view(self):
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(w)

        top = QHBoxLayout()
        title = QLabel("庐州非遗")
        title.setFont(QFont("STKaiti", 28, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        top.addWidget(title)
        top.addStretch()
        btn_back = QPushButton("返回")
        btn_back.setFixedSize(80, 36)
        btn_back.setStyleSheet("QPushButton { background: rgba(255,255,255,0.8); border: 1px solid #aaa; border-radius: 8px; } QPushButton:hover { background: rgba(255,255,255,1); }")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        top.addWidget(btn_back)
        layout.addLayout(top)

        content = QHBoxLayout()
        content.setSpacing(16)
        content.addWidget(self._intro_section(), stretch=1)
        content.addWidget(self._video_section(), stretch=3)
        content.addWidget(self._image_section(), stretch=1)
        layout.addLayout(content, stretch=5)

        nav = QHBoxLayout()
        nav.setAlignment(Qt.AlignCenter)
        nav.setSpacing(30)
        for name, slot in [("返回主页", self.go_home.emit), ("交互展示", self.go_viewer.emit)]:
            btn = QPushButton(name)
            btn.setFixedSize(140, 44)
            btn.setFont(QFont("Microsoft YaHei", 13))
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.8); border: 1px solid #aaa; border-radius: 8px; } QPushButton:hover { background: rgba(255,255,255,1); }")
            btn.clicked.connect(slot)
            nav.addWidget(btn)
        layout.addLayout(nav)
        return w

    def _intro_section(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: rgba(255,255,255,0.85); border-radius: 10px; padding: 12px; }")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        sections = [
            ("历史渊源", "合肥地区通过口述、戏盘、文字等形式流传千年的民间文学集群。故事围绕北宋名臣包拯的生平事迹展开。"),
            ("技艺特点", "以说唱结合为主要表现形式，融合庐剧唱腔和地方方言，具有浓郁的地域文化特色。"),
            ("传承现状", "2023年合肥文化馆通过开发文创产品、数字展陈等方式实现活态传承，入选省级非遗名录。"),
        ]
        for t, b in sections:
            tl = QLabel(t)
            tl.setFont(QFont("Microsoft YaHei", 13, QFont.Bold))
            tl.setStyleSheet("background: transparent;")
            layout.addWidget(tl)
            bl = QLabel(b)
            bl.setWordWrap(True)
            bl.setFont(QFont("Microsoft YaHei", 11))
            bl.setStyleSheet("background: transparent; color: #333;")
            layout.addWidget(bl)
        layout.addStretch()
        return frame

    def _video_section(self):
        frame = QFrame()
        frame.setStyleSheet("QFrame { background: rgba(255,255,255,0.85); border-radius: 10px; }")
        layout = QVBoxLayout(frame)
        label = QLabel("视频播放区")
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("background: rgba(0,0,0,0.1); border-radius: 8px; font-size: 18px; color: #888;")
        layout.addWidget(label)
        return frame

    def _image_section(self):
        frame = QFrame()
        frame.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        for i in range(3):
            img = QLabel(f"图片 {i+1}")
            img.setAlignment(Qt.AlignCenter)
            img.setStyleSheet("background: rgba(255,255,255,0.5); border: 1px dashed #aaa; border-radius: 6px; font-size: 14px; color: #888;")
            layout.addWidget(img, stretch=1)
        return frame