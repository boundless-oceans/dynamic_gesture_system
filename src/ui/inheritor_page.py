"""传承人风采页"""

import os

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPixmap
from src.ui.base_page import BasePage
from src.core import project_assets as _PA

_BTN_BASE="QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}"
_BTN_SEL="QPushButton{background:rgba(255,255,255,0.95);border:3px solid #ffb300;border-radius:25px;}QPushButton:hover{background:#fff;}"

NAMES = ["姚公庙姚氏", "肥西刘氏说书人", "合肥包公故事会", "丁玉兰", "刘凯", "邓之元"]
BODIES = [
    "姚氏葫芦雕刻世家，祖籍合肥姚公庙。第三代传人姚师傅自幼随父学艺，从事葫芦雕刻四十余年。作品以浮雕、镂空技法见长，题材涵盖人物、花鸟、山水，多次获省工艺美术展金奖。现为省级非遗传承人，在合肥设立工作室带徒传艺。",
    "肥西刘氏家族世代口传刘铭传故事，现年七旬的刘老先生为第五代传人。擅长以说书形式讲述刘铭传抗法保台、开发台湾的传奇经历，结合庐剧唱腔和合肥方言，声情并茂。每周在社区文化中心义务演出，培养年轻传承人。",
    "合肥包公故事会成立于2008年，由十余位民间说唱艺人组成。核心成员张老师研究包公文化三十余年，整理包公案、铡美案等经典故事近百篇。团队结合庐剧、快板、评书等多种形式，在合肥各社区巡回演出。",
    "丁玉兰，国家级非物质文化遗产庐剧代表性传承人。从艺六十余年，主攻花旦，嗓音甜美圆润，表演细腻传神。代表剧目《秦雪梅》《休丁香》等。曾任合肥庐剧团团长，培养大批庐剧人才，为庐剧振兴做出重要贡献。",
    "刘凯，安徽省非遗火笔画代表性传承人。自幼酷爱绘画，师从火笔画老艺人学艺二十余年。作品以山水、人物为主，运用不同温度烙铁烫出丰富的层次变化。在合肥设立火笔画传习所，定期举办培训交流活动。",
    "邓之元，省级非遗吴山铁字传承人。自幼随父学习锻铁技艺，将传统铁匠手艺与书法艺术完美结合。其铁字作品字体苍劲有力，曾作为合肥文化礼品赠送国际友人。在吴山镇建立铁字传承基地，带动当地文化产业发展。"
]


class InheritorPage(BasePage):
    go_home = Signal()

    def __init__(self):
        super().__init__()
        self._index = 0
        self._total = 6
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)

        title = QLabel("传承人风采")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 42, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title)

        top_row = QHBoxLayout()
        top_row.addStretch()
        btn_up = QPushButton("\u2191")
        btn_up.setFixedSize(50, 50)
        btn_up.setFont(QFont("Arial", 20))
        btn_up.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_up.clicked.connect(self._prev)
        top_row.addWidget(btn_up)
        layout.addLayout(top_row)

        # 主体：左侧文字 + 右侧视频
        content = QHBoxLayout()
        content.setSpacing(20)

        # 左侧
        left = QVBoxLayout()
        self._name_label = QLabel(NAMES[0])
        self._name_label.setFont(QFont("STKaiti", 28, QFont.Bold))
        self._name_label.setStyleSheet("background: transparent;")
        left.addWidget(self._name_label)

        self._body_label = QLabel(BODIES[0])
        self._body_label.setWordWrap(True)
        self._body_label.setFont(QFont("Microsoft YaHei", 13))
        self._body_label.setStyleSheet("background: transparent; color: #333;")
        self._body_label.setAlignment(Qt.AlignTop)
        left.addWidget(self._body_label, stretch=1)

        left_frame = QFrame()
        left_frame.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;padding:16px;}")
        left_frame.setLayout(left)
        content.addWidget(left_frame, stretch=1)

        # 右侧图片区（原来放视频，暂时改为项目图片）
        video_frame = QFrame()
        video_frame.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        vl = QVBoxLayout(video_frame)
        self._pic = QLabel()
        self._pic.setAlignment(Qt.AlignCenter)
        self._pic.setMinimumHeight(320)
        self._pic.setStyleSheet("background:rgba(0,0,0,0.06);border-radius:8px;")
        vl.addWidget(self._pic)
        content.addWidget(video_frame, stretch=2)

        layout.addLayout(content, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_down = QPushButton("\u2193")
        btn_down.setFixedSize(50, 50)
        btn_down.setFont(QFont("Arial", 20))
        btn_down.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_down.clicked.connect(lambda: self._on_btn(0))
        bottom_row.addWidget(btn_down)
        bottom_row.addSpacing(10)
        btn_back = QPushButton("\u21A9", self)
        btn_back.setFixedSize(50, 50)
        btn_back.setFont(QFont("Arial", 20))
        btn_back.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_back.clicked.connect(lambda: self._on_btn(1))
        bottom_row.addWidget(btn_back)
        layout.addLayout(bottom_row)

        # 可选中集合：[向下(翻页), 返回]，进入时默认选中"向下"
        self._sel=0
        self._sel_btns=[btn_down, btn_back]
        self._sel_actions=[self._next, self.go_home.emit]
        self._apply_sel()

    def _prev(self):
        self._index = (self._index - 1) % self._total
        self._update()

    def _next(self):
        self._index = (self._index + 1) % self._total
        self._update()

    def _on_btn(self, i):
        """鼠标点击按钮：同步选中态并执行"""
        self._sel = i; self._apply_sel(); self._sel_actions[i]()

    def select_prev(self):
        """向左：在[向下, 返回]间循环选中"""
        self._sel = (self._sel - 1) % len(self._sel_btns); self._apply_sel()

    def select_next(self):
        """向右：在[向下, 返回]间循环选中"""
        self._sel = (self._sel + 1) % len(self._sel_btns); self._apply_sel()

    def activate_selected(self):
        """确认：执行当前选中按钮"""
        self._sel_actions[self._sel]()

    def _apply_sel(self):
        for i, b in enumerate(self._sel_btns):
            b.setStyleSheet(_BTN_SEL if i == self._sel else _BTN_BASE)

    def _update(self):
        self._name_label.setText(NAMES[self._index])
        self._body_label.setText(BODIES[self._index])
        self._load_pic()

    def _load_pic(self):
        """按传承人序号加载对应项目的配图（顺序与 assets/projects.json 一致）
        用 portrait.jpg（与首页卡片图不同，避免重复）；缺失时回退卡片图"""
        path = _PA.portrait_path(self._index)
        if path and os.path.exists(path):
            self._pic.setPixmap(QPixmap(path).scaled(
                560, 420, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._pic.setStyleSheet("background:rgba(0,0,0,0.06);border-radius:8px;")
        else:
            self._pic.setPixmap(QPixmap())
            self._pic.setText("暂无图片")
            self._pic.setStyleSheet("background:rgba(0,0,0,0.06);border-radius:8px;font-size:16px;color:#888;")
