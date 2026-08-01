"""详情页"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QFrame
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from src.ui.base_page import BasePage

PROJECTS = [
    {"name": "葫芦雕刻", "sections": [
        ("历史渊源", "葫芦雕刻起源于宋代，合肥地区民间艺人以葫芦为载体，运用刻、烙、绘等技法创作出精美的工艺品。"),
        ("技艺特点", "以刀代笔进行浮雕、镂空处理，讲究构图饱满线条流畅，融合中国画白描与民间剪纸特色。"),
        ("传承现状", "多位省市级非遗传承人，通过工作室、进校园等方式培养后继人才，作品多次获奖。"),
    ]},
    {"name": "刘铭传故事", "sections": [
        ("历史渊源", "刘铭传（1836-1896），安徽合肥人，清末淮军名将、台湾首任巡抚。其事迹在合肥民间广为流传。"),
        ("技艺特点", "以说书、戏曲等形式讲述刘铭传抗法保台故事，融合庐剧唱腔和合肥方言，声情并茂。"),
        ("传承现状", "多个社区和文化团体定期举办刘铭传故事会，2021年列入市级非遗保护名录。"),
    ]},
    {"name": "包公故事", "sections": [
        ("历史渊源", "合肥地区通过口述、戏盘、文字等形式流传千年的民间文学集群。故事围绕北宋名臣包拯的生平事迹展开。"),
        ("技艺特点", "以说唱结合为主要表现形式，融合庐剧唱腔和地方方言，具有浓郁的地域文化特色。"),
        ("传承现状", "2023年合肥文化馆通过开发文创产品、数字展陈等方式实现活态传承，入选省级非遗名录。"),
    ]},
    {"name": "庐剧", "sections": [
        ("历史渊源", "庐剧原名倒七戏，是安徽省主要地方戏曲剧种之一，流行于江淮一带，已有近两百年历史。"),
        ("技艺特点", "唱腔丰富多样，分主调和花腔两大类。表演朴实细腻，伴奏以锣鼓为主，乡土气息浓郁。"),
        ("传承现状", "合肥庐剧院为传承主力，2006年入选首批国家级非遗名录，现有国家级传承人3位。"),
    ]},
    {"name": "火笔画", "sections": [
        ("历史渊源", "火笔画以铁扦为笔、以火为墨在木板纸张上烙绘，源于清代，是江淮独有的民间美术形式。"),
        ("技艺特点", "运用不同温度烙铁烫出深浅褐色痕迹，一笔成型不可修改，古朴典雅层次丰富。"),
        ("传承现状", "多位省市级传承人，合肥市设立火笔画传习所，作品被多家博物馆收藏。"),
    ]},
    {"name": "吴山铁字", "sections": [
        ("历史渊源", "吴山铁字源于肥西县吴山镇，是铁画艺术的延伸。以铁为墨、以锤为笔锻打书法作品。"),
        ("技艺特点", "书法与锻造工艺结合，字体苍劲有力浑然天成，具独特金属质感和装饰效果。"),
        ("传承现状", "省级非遗项目，吴山镇建立铁字传承基地，作品远销海内外，成为合肥文化名片。"),
    ]},
]


class DetailPage(BasePage):
    go_home = Signal()
    go_viewer = Signal()

    def __init__(self, project_index: int = 2):
        super().__init__()
        self.project = PROJECTS[project_index]
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        self.stack.addWidget(self._main())
        self.stack.addWidget(self._detail())
        layout.addWidget(self.stack)

    def set_project(self, i: int):
        self.project = PROJECTS[i]
        while self.stack.count():
            self.stack.removeWidget(self.stack.widget(0))
        self.stack.addWidget(self._main())
        self.stack.addWidget(self._detail())
        self.stack.setCurrentIndex(0)

    def reset_to_main(self): self.stack.setCurrentIndex(0)

    def _main(self):
        w = QWidget(); w.setStyleSheet("background: transparent;")
        l = QVBoxLayout(w)
        t = QLabel(self.project["name"]); t.setAlignment(Qt.AlignCenter)
        t.setFont(QFont("STKaiti", 42, QFont.Bold)); t.setStyleSheet("background: transparent;")
        l.addWidget(t, stretch=1)
        ph = QLabel("3D 模型预览区"); ph.setAlignment(Qt.AlignCenter)
        ph.setStyleSheet("background: rgba(255,255,255,0.3); border: 2px dashed #aaa; border-radius: 16px; font-size: 20px; color: #666;")
        l.addWidget(ph, stretch=4)
        bl = QHBoxLayout(); bl.setAlignment(Qt.AlignCenter); bl.setSpacing(30)
        for text, slot in [("返回主页", self.go_home.emit), ("非遗详情", lambda: self.stack.setCurrentIndex(1)), ("交互展示", self.go_viewer.emit)]:
            btn = QPushButton(text); btn.setFixedSize(140, 50); btn.setFont(QFont("Microsoft YaHei", 14))
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.45); border: 1px solid rgba(255,255,255,0.6); border-radius: 10px; } QPushButton:hover { background: rgba(255,255,255,0.85); }")
            btn.clicked.connect(slot); bl.addWidget(btn)
        l.addLayout(bl, stretch=1)
        return w

    def _detail(self):
        w = QWidget(); w.setStyleSheet("background: transparent;")
        l = QVBoxLayout(w)
        top = QHBoxLayout()
        t = QLabel("庐州非遗"); t.setFont(QFont("STKaiti", 28, QFont.Bold)); t.setStyleSheet("background: transparent;")
        top.addWidget(t); top.addStretch()
        bk = QPushButton("返回"); bk.setFixedSize(80, 36)
        bk.setStyleSheet("QPushButton { background: rgba(255,255,255,0.45); border: 1px solid rgba(255,255,255,0.6); border-radius: 8px; } QPushButton:hover { background: rgba(255,255,255,0.85); }")
        bk.clicked.connect(lambda: self.stack.setCurrentIndex(0)); top.addWidget(bk)
        l.addLayout(top)
        c = QHBoxLayout(); c.setSpacing(16)
        c.addWidget(self._intro(), stretch=1); c.addWidget(self._video(), stretch=3); c.addWidget(self._imgs(), stretch=1)
        l.addLayout(c, stretch=5)
        nav = QHBoxLayout(); nav.setAlignment(Qt.AlignCenter); nav.setSpacing(30)
        for name, slot in [("返回主页", self.go_home.emit), ("交互展示", self.go_viewer.emit)]:
            btn = QPushButton(name); btn.setFixedSize(140, 44); btn.setFont(QFont("Microsoft YaHei", 13))
            btn.setStyleSheet("QPushButton { background: rgba(255,255,255,0.45); border: 1px solid rgba(255,255,255,0.6); border-radius: 8px; } QPushButton:hover { background: rgba(255,255,255,0.85); }")
            btn.clicked.connect(slot); nav.addWidget(btn)
        l.addLayout(nav)
        return w

    def _intro(self):
        f = QFrame()
        f.setStyleSheet("QFrame { background: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.6); border-radius: 16px; padding: 14px; }")
        l = QVBoxLayout(f); l.setSpacing(10)
        for ti, bo in self.project["sections"]:
            tl = QLabel(ti); tl.setFont(QFont("Microsoft YaHei", 13, QFont.Bold)); tl.setStyleSheet("background: transparent;"); l.addWidget(tl)
            bl = QLabel(bo); bl.setWordWrap(True); bl.setFont(QFont("Microsoft YaHei", 11)); bl.setStyleSheet("background: transparent; color: #333;"); l.addWidget(bl)
        l.addStretch()
        return f

    def _video(self):
        f = QFrame(); f.setStyleSheet("QFrame { background: rgba(255,255,255,0.5); border: 1px solid rgba(255,255,255,0.6); border-radius: 16px; }")
        l = QVBoxLayout(f); lb = QLabel("视频播放区"); lb.setAlignment(Qt.AlignCenter)
        lb.setStyleSheet("background: rgba(0,0,0,0.1); border-radius: 8px; font-size: 18px; color: #888;"); l.addWidget(lb)
        return f

    def _imgs(self):
        f = QFrame(); f.setStyleSheet("background: transparent;")
        l = QVBoxLayout(f); l.setSpacing(10)
        for i in range(3):
            img = QLabel(f"图片 {i+1}"); img.setAlignment(Qt.AlignCenter)
            img.setStyleSheet("background: rgba(255,255,255,0.5); border: 1px dashed #aaa; border-radius: 6px; font-size: 14px; color: #888;")
            l.addWidget(img, stretch=1)
        return f