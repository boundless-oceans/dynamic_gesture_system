"""详情页"""
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QFrame,QGraphicsDropShadowEffect
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QFont,QColor
from src.core.project_data import PROJECTS, get_sections
from src.ui.hover_button import HoverButton
from src.ui.base_page import BasePage

_BTN_NORMAL="QPushButton{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:10px;}QPushButton:hover{background:rgba(255,255,255,0.85);}"
_BTN_SEL="QPushButton{background:rgba(255,255,255,0.92);border:3px solid #ffb300;border-radius:12px;}QPushButton:hover{background:#fff;}"

P=[{"n":"葫芦雕刻","s":[("历史渊源","源于宋代，合肥民间艺人以葫芦为载体运用刻烙绘等技法。"),("技艺特点","以刀代笔浮雕镂空，构图饱满线条流畅。"),("传承现状","多位省市级传承人，通过工作室进校园培养后继人才。")]},
   {"n":"刘铭传故事","s":[("历史渊源","刘铭传，安徽合肥人，清末淮军名将、台湾首任巡抚。"),("技艺特点","说书戏曲形式融合庐剧唱腔和合肥方言。"),("传承现状","多个社区定期举办故事会，列入市级非遗。")]},
   {"n":"包公故事","s":[("历史渊源","合肥流传千年的民间文学，围绕北宋名臣包拯生平事迹展开。"),("技艺特点","说唱结合融合庐剧唱腔，地方文化特色浓郁。"),("传承现状","2023年通过文创产品数字展陈实现活态传承。")]},
   {"n":"庐剧","s":[("历史渊源","庐剧原名倒七戏，安徽主要地方剧种，流行江淮近两百年。"),("技艺特点","唱腔丰富分主调花腔，表演朴实以锣鼓伴奏为主。"),("传承现状","合肥庐剧院传承主力，入选首批国家级非遗。")]},
   {"n":"火笔画","s":[("历史渊源","以铁扦为笔以火为墨烙绘，源于清代江淮独有民间美术形式。"),("技艺特点","不同温度烙铁烫出深浅褐色痕迹，一笔成型不可修改。"),("传承现状","合肥设传习所，多位传承人，作品被博物馆收藏。")]},
   {"n":"吴山铁字","s":[("历史渊源","源于肥西吴山镇铁画延伸，以铁为墨以锤为笔。"),("技艺特点","书法与锻造结合，字体苍劲有力具独特金属质感。"),("传承现状","省级非遗，吴山镇建基地，作品成合肥文化名片。")]}]

class DetailPage(BasePage):
    go_home=Signal(); go_viewer=Signal()
    def __init__(self,pi=2):
        super().__init__(); self._pi=pi
        # 主视图三个按钮的选中状态（手势左/右切换）
        self._sel=0; self._btns=[]; self._actions=[]

        self.setAttribute(Qt.WA_StyledBackground,False)
        lo=QVBoxLayout(self); lo.setContentsMargins(20,20,20,40)
        self.stack=QStackedWidget(); self.stack.setStyleSheet("background:transparent;")
        self.stack.addWidget(self._m()); self.stack.addWidget(self._d())
        lo.addWidget(self.stack)
    def set_project(self,i): self._pi=i; self._rb()
    def reset_to_main(self): self.stack.setCurrentIndex(0)
    def _rb(self):
        while self.stack.count(): self.stack.removeWidget(self.stack.widget(0))
        self.stack.addWidget(self._m()); self.stack.addWidget(self._d())
        self.stack.setCurrentIndex(0)
    def _m(self):
        w=QWidget(); w.setStyleSheet("background:transparent;"); l=QVBoxLayout(w)
        t=QLabel(PROJECTS[self._pi]["name"]); t.setAlignment(Qt.AlignCenter)
        t.setFont(QFont("STKaiti",42,QFont.Bold)); t.setStyleSheet("background:transparent;")
        l.addWidget(t,stretch=1)
        ph=QLabel("3D 模型预览区"); ph.setAlignment(Qt.AlignCenter)
        ph.setStyleSheet("background:rgba(255,255,255,0.3);border:2px dashed #aaa;border-radius:16px;font-size:20px;color:#666;")
        l.addWidget(ph,stretch=4)
        bl=QHBoxLayout(); bl.setAlignment(Qt.AlignCenter); bl.setSpacing(30)
        self._btns=[]; self._actions=[]
        specs=[("返回主页",self.go_home.emit),("非遗详情",lambda:self.stack.setCurrentIndex(1)),("交互展示",self.go_viewer.emit)]
        for i,(tx,sl) in enumerate(specs):
            b=HoverButton(tx); b.setFixedSize(140,50); b.setFont(QFont("Microsoft YaHei",14))
            b.clicked.connect(lambda _=False, i=i: self._on_btn(i))
            self._btns.append(b); self._actions.append(sl); bl.addWidget(b)
        l.addLayout(bl,stretch=1)
        if self._sel >= len(self._btns): self._sel=0
        self._apply_sel()
        return w

    def _on_btn(self,i):
        self._sel=i; self._apply_sel(); self._actions[i]()

    def select_prev(self):
        """向左：选中左移一格，最左再向左循环到最右"""
        if not self._btns: return
        self._sel=(self._sel-1)%len(self._btns); self._apply_sel()

    def select_next(self):
        """向右：选中右移一格，最右再向右循环到最左"""
        if not self._btns: return
        self._sel=(self._sel+1)%len(self._btns); self._apply_sel()

    def activate_selected(self):
        """激活当前选中的按钮"""
        if self._btns: self._actions[self._sel]()

    def _apply_sel(self):
        for i,b in enumerate(self._btns):
            if i==self._sel:
                glow=QGraphicsDropShadowEffect(); glow.setBlurRadius(28)
                glow.setColor(QColor(255,180,0,230)); glow.setOffset(0,0)
                b.setGraphicsEffect(glow); b.setStyleSheet(_BTN_SEL)
            else:
                b.setGraphicsEffect(None); b.setStyleSheet(_BTN_NORMAL)
    def _d(self):
        w=QWidget(); w.setStyleSheet("background:transparent;"); l=QVBoxLayout(w)
        top=QHBoxLayout(); t=QLabel("庐州非遗"); t.setFont(QFont("STKaiti",28,QFont.Bold))
        t.setStyleSheet("background:transparent;"); top.addWidget(t); top.addStretch()
        l.addLayout(top)
        c=QHBoxLayout(); c.setSpacing(16)
        c.addWidget(self._i(),stretch=2); c.addWidget(self._v(),stretch=6); c.addWidget(self._im(),stretch=3)
        l.addLayout(c,stretch=10)
        bottom=QHBoxLayout(); bottom.addStretch()
        btn=QPushButton("\u21A9",w); btn.setFixedSize(60,60); btn.setFont(QFont("Arial",24))
        btn.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:30px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn.clicked.connect(lambda:self.stack.setCurrentIndex(0))
        bottom.addWidget(btn); l.addLayout(bottom)
        return w
    def _i(self):
        f=QFrame(); f.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;padding:14px;}")
        lo=QVBoxLayout(f); lo.setSpacing(7)
        for ti,bo in get_sections(self._pi):
            a=QLabel(ti); a.setFont(QFont("Microsoft YaHei",11,QFont.Bold)); a.setStyleSheet("background:transparent;"); lo.addWidget(a)
            b=QLabel(bo); b.setMinimumHeight(60); b.setWordWrap(True); b.setFont(QFont("Microsoft YaHei",11)); b.setStyleSheet("background:transparent;color:#333;"); lo.addWidget(b)
        lo.addStretch(); return f
    def _v(self):
        f=QFrame(); f.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        lo=QVBoxLayout(f); lb=QLabel("视频播放区"); lb.setAlignment(Qt.AlignCenter)
        lb.setStyleSheet("background:rgba(0,0,0,0.1);border-radius:8px;font-size:18px;color:#888;"); lo.addWidget(lb); return f
    def _im(self):
        f=QFrame(); f.setStyleSheet("background:transparent;"); lo=QVBoxLayout(f); lo.setSpacing(8)
        lo.setContentsMargins(0,0,0,0)
        for i in range(3):
            im=QLabel(f"图片 {i+1}"); im.setAlignment(Qt.AlignCenter); im.setMinimumHeight(96)
            im.setStyleSheet("background:rgba(255,255,255,0.5);border:1px dashed #aaa;border-radius:6px;font-size:14px;color:#888;")
            lo.addWidget(im,stretch=1)
        return f
