"""详情页"""
import os

from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QStackedWidget,QFrame,QScrollArea
from PySide6.QtCore import Qt,Signal,QUrl,QTimer
from PySide6.QtGui import QFont,QPixmap
from PySide6.QtMultimedia import QMediaPlayer,QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from src.core.project_data import PROJECTS, get_sections
from src.core import project_assets as _PA
from src.ui.hover_button import HoverButton
from src.ui.base_page import BasePage

# 选中用金色边框表示；不改动 HoverButton 原本的浮动阴影
_BTN_NORMAL="QPushButton{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:10px;}QPushButton:hover{background:rgba(255,255,255,0.85);}"
_BTN_SEL="QPushButton{background:rgba(255,255,255,0.92);border:3px solid #ffb300;border-radius:12px;}QPushButton:hover{background:#fff;}"
_BACK_SEL="QPushButton{background:rgba(255,255,255,0.95);border:3px solid #ffb300;border-radius:30px;}QPushButton:hover{background:#fff;}"


class _FitLabel(QLabel):
    """按控件实际大小自动等比缩放图片，避免被裁切（二维码等竖版图尤其需要）"""
    def __init__(self, path, pad=6, parent=None):
        super().__init__(parent)
        self._orig = QPixmap(path)
        self._pad = pad
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumHeight(60)
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._rescale()
    def showEvent(self, e):
        super().showEvent(e)
        self._rescale()
    def _rescale(self):
        if self._orig.isNull():
            return
        w = max(1, self.width() - 2*self._pad)
        h = max(1, self.height() - 2*self._pad)
        self.setPixmap(self._orig.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))

P=[{"n":"葫芦烙画","s":[("历史渊源","源于宋代，合肥民间艺人以葫芦为载体运用刻烙绘等技法。"),("技艺特点","以刀代笔浮雕镂空，构图饱满线条流畅。"),("传承现状","多位省市级传承人，通过工作室进校园培养后继人才。")]},
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
        # 视频播放器（仅非遗详情子页使用）
        self._player=None; self._audio=None; self._vwidget=None

        self.setAttribute(Qt.WA_StyledBackground,False)
        lo=QVBoxLayout(self); lo.setContentsMargins(20,20,20,40)
        self.stack=QStackedWidget(); self.stack.setStyleSheet("background:transparent;")
        self.stack.addWidget(self._m()); self.stack.addWidget(self._d())
        self.stack.currentChanged.connect(self._on_subpage)
        lo.addWidget(self.stack)
        # 主视图作品轮播：自动切换
        self._slide_idx=0; self._slides=[]
        self._slide_timer=QTimer(self); self._slide_timer.setInterval(3500)
        self._slide_timer.timeout.connect(self._tick_slide); self._slide_timer.start()
    def _tick_slide(self):
        # 只在"主视图且页面可见"时轮播
        if not self.isVisible() or self.stack.currentIndex()!=0: return
        self.next_slide()
    def set_project(self,i): self._pi=i; self._rb()
    def reset_to_main(self): self.stack.setCurrentIndex(0)
    def _on_subpage(self, idx):
        """离开非遗详情子页时暂停视频，回来时继续"""
        if idx != 1:
            self.pause_video()
        else:
            self.resume_video()
    def _rb(self):
        self._dispose_video()
        while self.stack.count(): self.stack.removeWidget(self.stack.widget(0))
        self.stack.addWidget(self._m()); self.stack.addWidget(self._d())
        self.stack.setCurrentIndex(0)
    def _dispose_video(self):
        """切项目/重建时释放播放器"""
        if self._player is not None:
            self._player.stop()
            self._player.setSource(QUrl())
            self._player = None
        self._audio = None
        self._vwidget = None
    def pause_video(self):
        if self._player is not None:
            self._player.pause()
    def resume_video(self):
        if self._player is not None:
            self._player.play()
    def is_video_view(self) -> bool:
        """当前是否在"非遗详情"子页（有视频的那页）"""
        return self.stack.currentIndex()==1
    def seek(self, delta_ms):
        """左/右抛出：视频快退/快进"""
        if self._player is not None:
            self._player.setPosition(max(0, self._player.position()+delta_ms))
    def showEvent(self,e):
        super().showEvent(e)
        if self.stack.currentIndex()==1: self.resume_video()
    def hideEvent(self,e):
        super().hideEvent(e)
        self.pause_video()
    def _m(self):
        w=QWidget(); w.setStyleSheet("background:transparent;"); l=QVBoxLayout(w)
        t=QLabel(PROJECTS[self._pi]["name"]); t.setAlignment(Qt.AlignCenter)
        t.setFont(QFont("STKaiti",42,QFont.Bold)); t.setStyleSheet("background:transparent;")
        l.addWidget(t,stretch=1)

        # 主体：左=作品轮播，右=项目信息卡
        row=QHBoxLayout(); row.setSpacing(20)

        self._slides=_PA.slide_paths(self._pi)
        self._slide_stack=QStackedWidget()
        self._slide_stack.setStyleSheet("background:transparent;")
        if self._slides:
            for p in self._slides:
                self._slide_stack.addWidget(_FitLabel(p, pad=10))
            self._slide_idx=0
        else:
            ph=QLabel("作品图片待补充"); ph.setAlignment(Qt.AlignCenter)
            ph.setStyleSheet("background:rgba(255,255,255,0.4);border:2px dashed #aaa;border-radius:16px;font-size:18px;color:#666;")
            self._slide_stack.addWidget(ph); self._slide_idx=0
        slide_frame=QFrame()
        slide_frame.setStyleSheet("QFrame{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        sf=QVBoxLayout(slide_frame); sf.setContentsMargins(8,8,8,8); sf.addWidget(self._slide_stack)
        # 页码指示（● ○ ○）
        self._dots=QLabel(""); self._dots.setAlignment(Qt.AlignCenter)
        self._dots.setStyleSheet("background:transparent;color:#ff9900;font-size:14px;")
        sf.addWidget(self._dots)
        row.addWidget(slide_frame, stretch=3)

        # 信息卡整体下移，避开右上角常驻的摄像头悬浮窗（320x240）
        info_col=QVBoxLayout(); info_col.setContentsMargins(0,0,0,0)
        info_col.addSpacing(110)
        info_col.addWidget(self._info_card())
        row.addLayout(info_col, stretch=2)
        l.addLayout(row, stretch=4)
        self._update_slide_ui()

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

    def _info_card(self):
        """项目信息卡：级别 / 类别 / 传承人 / 一句话简介（取自 assets/projects.json）"""
        it=PROJECTS[self._pi]
        f=QFrame()
        f.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        lo=QVBoxLayout(f); lo.setContentsMargins(20,18,20,18); lo.setSpacing(8)
        def row(k,v):
            h=QHBoxLayout(); h.setSpacing(8)
            a=QLabel(k); a.setFixedWidth(52); a.setFont(QFont("Microsoft YaHei",12))
            a.setStyleSheet("background:transparent;color:#888;")
            b=QLabel(v or "—"); b.setWordWrap(True); b.setFont(QFont("Microsoft YaHei",13,QFont.Bold))
            b.setStyleSheet("background:transparent;color:#333;")
            h.addWidget(a); h.addWidget(b,stretch=1); return h
        # 级别不占行（放进简介文字里），把空间留给介绍正文
        lo.addLayout(row("类别", it.get("category","")))
        lo.addLayout(row("传承人", it.get("inheritor","")))
        line=QFrame(); line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color:rgba(0,0,0,0.12);"); lo.addWidget(line)
        # 详细介绍：放进滚动区，文字多时不被裁切（可用滚轮查看）
        inner=QWidget(); inner.setStyleSheet("background:transparent;")
        il=QVBoxLayout(inner); il.setContentsMargins(0,0,6,0)
        sm=QLabel(it.get("intro") or it.get("summary","")); sm.setWordWrap(True)
        sm.setFont(QFont("Microsoft YaHei",12)); sm.setStyleSheet("background:transparent;color:#555;")
        sm.setAlignment(Qt.AlignTop); il.addWidget(sm); il.addStretch()
        sa=QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                         "QScrollArea > QWidget > QWidget{background:transparent;}"
                         "QScrollBar:vertical{width:8px;background:transparent;}"
                         "QScrollBar::handle:vertical{background:rgba(0,0,0,0.25);border-radius:4px;}"
                         "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        sa.setWidget(inner)
        lo.addWidget(sa, stretch=1)
        return f

    def _update_slide_ui(self):
        self._slide_stack.setCurrentIndex(self._slide_idx)
        n=len(self._slides)
        self._dots.setText(" ".join("●" if i==self._slide_idx else "○" for i in range(n)) if n else "")

    def next_slide(self):
        if len(self._slides) > 1:
            self._slide_idx = (self._slide_idx + 1) % len(self._slides)
            self._update_slide_ui()

    def _on_btn(self,i):
        self._sel=i; self._apply_sel(); self._actions[i]()

    def select_prev(self):
        """向左：选中左移一格，最左再向左循环到最右（非遗详情子页只有返回键，不切换）"""
        if self.stack.currentIndex()==1 or not self._btns: return
        self._sel=(self._sel-1)%len(self._btns); self._apply_sel()

    def select_next(self):
        """向右：选中右移一格，最右再向右循环到最左（非遗详情子页只有返回键，不切换）"""
        if self.stack.currentIndex()==1 or not self._btns: return
        self._sel=(self._sel+1)%len(self._btns); self._apply_sel()

    def activate_selected(self):
        """确认：非遗详情子页=返回主视图；主视图=激活选中按钮"""
        if self.stack.currentIndex()==1:
            self.stack.setCurrentIndex(0); return
        if self._btns: self._actions[self._sel]()

    def _apply_sel(self):
        # 仅用金色边框标记选中，保留 HoverButton 的浮动阴影效果
        for i,b in enumerate(self._btns):
            b.setStyleSheet(_BTN_SEL if i==self._sel else _BTN_NORMAL)
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
        # \u975E\u9057\u8BE6\u60C5\u5B50\u9875\uFF1A\u8FD4\u56DE\u952E\u9ED8\u8BA4\u9009\u4E2D\uFF08\u91D1\u8FB9\uFF09\uFF0C\u70B9\u51FB/\u786E\u8BA4=\u8FD4\u56DE\u4E3B\u89C6\u56FE
        btn.setStyleSheet(_BACK_SEL)
        btn.clicked.connect(lambda:self.stack.setCurrentIndex(0))
        bottom.addWidget(btn); l.addLayout(bottom)
        return w
    def _i(self):
        f=QFrame(); f.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        # 文字内容用滚动区包裹：框不够高时可滚动查看，避免文字被裁掉
        inner=QWidget(); inner.setStyleSheet("background:transparent;")
        lo=QVBoxLayout(inner); lo.setSpacing(10); lo.setContentsMargins(14,14,14,14)
        for ti,bo in get_sections(self._pi):
            a=QLabel(ti); a.setFont(QFont("Microsoft YaHei",11,QFont.Bold)); a.setStyleSheet("background:transparent;"); lo.addWidget(a)
            b=QLabel(bo); b.setWordWrap(True); b.setMinimumHeight(40)
            b.setFont(QFont("Microsoft YaHei",11)); b.setStyleSheet("background:transparent;color:#333;"); lo.addWidget(b)
        lo.addStretch()
        sa=QScrollArea(); sa.setWidgetResizable(True); sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                         "QScrollArea > QWidget > QWidget{background:transparent;}"
                         "QScrollBar:vertical{width:8px;background:transparent;}"
                         "QScrollBar::handle:vertical{background:rgba(0,0,0,0.25);border-radius:4px;}"
                         "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        sa.setWidget(inner)
        outer=QVBoxLayout(f); outer.setContentsMargins(0,0,0,0); outer.addWidget(sa)
        return f
    def _v(self):
        f=QFrame(); f.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        lo=QVBoxLayout(f)
        path=_PA.video_path(self._pi)
        if path:
            self._player=QMediaPlayer(self)
            self._audio=QAudioOutput(self); self._audio.setVolume(0.6)
            self._player.setAudioOutput(self._audio)
            vw=QVideoWidget(); vw.setAspectRatioMode(Qt.KeepAspectRatio)
            self._player.setVideoOutput(vw)
            self._player.setLoops(QMediaPlayer.Infinite)     # 循环播放
            self._player.setSource(QUrl.fromLocalFile(path))
            self._player.play()
            self._vwidget=vw
            lo.addWidget(vw)
        else:
            lb=QLabel("暂无视频"); lb.setAlignment(Qt.AlignCenter)
            lb.setStyleSheet("background:rgba(0,0,0,0.1);border-radius:8px;font-size:18px;color:#888;")
            lo.addWidget(lb)
        return f
    def _im(self):
        f=QFrame(); f.setStyleSheet("background:transparent;"); lo=QVBoxLayout(f); lo.setSpacing(8)
        lo.setContentsMargins(0,0,0,0)
        for i in range(3):
            # 第 3 张：优先显示项目二维码（扫码了解），没有二维码时用详情图
            path = (_PA.qr_path(self._pi) or _PA.detail_path(self._pi, 3)) if i == 2 \
                   else _PA.detail_path(self._pi, i+1)
            if path and os.path.exists(path):
                im = _FitLabel(path)      # 自适应缩放，不会被裁切
                im.setStyleSheet("background:#fff;border:1px solid rgba(255,255,255,0.6);border-radius:6px;"
                                 if i == 2 else
                                 "background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:6px;")
            else:
                im=QLabel(f"图片 {i+1}"); im.setAlignment(Qt.AlignCenter); im.setMinimumHeight(60)
                im.setStyleSheet("background:rgba(255,255,255,0.5);border:1px dashed #aaa;border-radius:6px;font-size:14px;color:#888;")
            lo.addWidget(im,stretch=1)
        return f
