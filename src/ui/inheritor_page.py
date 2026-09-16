"""传承人风采页"""

import os

from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame, QStackedWidget, QWidget
from PySide6.QtCore import Qt, Signal, QUrl
from PySide6.QtGui import QFont, QPixmap
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from src.ui.base_page import BasePage
from src.core import project_assets as _PA
from src import config

def _load_inheritors() -> list:
    """读取 assets/inheritors.json（传承人页数据）"""
    import json
    path = os.path.join(os.path.dirname(__file__), "../../assets/inheritors.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get("items", [])
    except Exception as e:
        print(f"[inheritor] 读取 inheritors.json 失败: {e}")
        return []


INHERITORS = _load_inheritors()


class InheritorPage(BasePage):
    go_home = Signal()

    def __init__(self):
        super().__init__()
        self._index = 0
        self._total = max(1, len(INHERITORS))
        # 视频播放器（有对应视频时播放，否则显示照片）
        self._player = None; self._audio = None; self._vwidget = None
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 20)

        title = QLabel("传承人风采")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 42, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title)

        # \u4e0a/\u4e0b\u4e00\u4f4d\u6309\u94ae\u7edf\u4e00\u653e\u5728\u53f3\u4e0b\u89d2\uff08\u907f\u5f00\u53f3\u4e0a\u89d2\u6444\u50cf\u5934\u60ac\u6d6e\u7a97\uff09

        # 主体：左侧文字 + 右侧视频
        content = QHBoxLayout()
        content.setSpacing(20)

        # 左侧
        left = QVBoxLayout()
        self._name_label = QLabel(INHERITORS[0]["name"] if INHERITORS else "")
        self._name_label.setFont(QFont("STKaiti", 28, QFont.Bold))
        self._name_label.setStyleSheet("background: transparent;")
        left.addWidget(self._name_label)

        self._body_label = QLabel("")
        self._body_label.setWordWrap(True)
        self._body_label.setFont(QFont("Microsoft YaHei", 13))
        self._body_label.setStyleSheet("background: transparent; color: #333;")
        self._body_label.setAlignment(Qt.AlignTop)
        left.addWidget(self._body_label, stretch=1)

        left_frame = QFrame()
        left_frame.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;padding:16px;}")
        left_frame.setLayout(left)
        content.addWidget(left_frame, stretch=1)

        # 右侧：有视频放视频，没有则显示照片
        video_frame = QFrame()
        video_frame.setStyleSheet("QFrame{background:rgba(255,255,255,0.5);border:1px solid rgba(255,255,255,0.6);border-radius:16px;}")
        vl = QVBoxLayout(video_frame)
        self._media = QStackedWidget()
        self._pic = QLabel()
        self._pic.setAlignment(Qt.AlignCenter)
        self._pic.setMinimumHeight(320)
        self._pic.setStyleSheet("background:rgba(0,0,0,0.06);border-radius:8px;")
        self._media.addWidget(self._pic)              # 0: 照片
        self._video_holder = QWidget()
        self._vh_lo = QVBoxLayout(self._video_holder); self._vh_lo.setContentsMargins(0,0,0,0)
        self._media.addWidget(self._video_holder)     # 1: 视频
        vl.addWidget(self._media)
        # 右侧视频略微下移，给右上角摄像头悬浮窗让出主要空间；
        # 若仍有少量重叠，摄像头在最上层（内容不会盖住画面）
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.addSpacing(160)          # 让开右上角摄像头悬浮窗(高240)，避免遮挡
        right_col.addWidget(video_frame)
        content.addLayout(right_col, stretch=2)

        layout.addLayout(content, stretch=1)

        bottom_row = QHBoxLayout()
        bottom_row.addStretch()
        btn_up = QPushButton("\u2191")
        btn_up.setFixedSize(50, 50)
        btn_up.setFont(QFont("Arial", 20))
        btn_up.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_up.clicked.connect(self._prev)
        bottom_row.addWidget(btn_up)
        bottom_row.addSpacing(10)
        btn_down = QPushButton("\u2193")
        btn_down.setFixedSize(50, 50)
        btn_down.setFont(QFont("Arial", 20))
        btn_down.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_down.clicked.connect(self._next)
        bottom_row.addWidget(btn_down)
        bottom_row.addSpacing(10)
        btn_back = QPushButton("\u21A9", self)
        btn_back.setFixedSize(50, 50)
        btn_back.setFont(QFont("Arial", 20))
        btn_back.setStyleSheet("QPushButton{background:rgba(255,255,255,0.5);border:none;border-radius:25px;}QPushButton:hover{background:rgba(255,255,255,0.9);}")
        btn_back.clicked.connect(self.go_home.emit)
        bottom_row.addWidget(btn_back)
        layout.addLayout(bottom_row)

        # 手势：左/右=视频快退/快进，向下抛出=下一位，点击=返回
        self._update()

    def _prev(self):
        self._index = (self._index - 1) % self._total
        self._update()

    def _next(self):
        self._index = (self._index + 1) % self._total
        self._update()

    # ---- 手势接口 ----
    def next_person(self):
        """向下抛出：下一位传承人"""
        self._next()

    def prev_person(self):
        """向上抛出：上一位传承人"""
        self._prev()

    def seek(self, delta_ms):
        """左/右抛出：视频快退/快进"""
        if self._player is not None:
            self._player.setPosition(max(0, self._player.position() + delta_ms))

    def seek_back(self):
        self.seek(-config.SEEK_STEP_MS)

    def seek_forward(self):
        self.seek(config.SEEK_STEP_MS)

    def confirm(self):
        """点击：返回"""
        self.go_home.emit()

    def resume(self):
        if self._player is not None:
            self._player.play()

    def showEvent(self, e):
        super().showEvent(e)
        self.resume()

    def hideEvent(self, e):
        super().hideEvent(e)
        if self._player is not None:
            self._player.pause()

    def _dispose_player(self):
        if self._player is not None:
            self._player.stop(); self._player.setSource(QUrl()); self._player = None
            self._audio = None
        if self._vwidget is not None:
            self._vwidget.setParent(None); self._vwidget.deleteLater(); self._vwidget = None

    def _load_media(self):
        """有对应视频就放视频，否则显示照片"""
        self._dispose_player()
        it = INHERITORS[self._index] if INHERITORS else {}
        vpath = _PA.inheritor_video(it.get("video", ""))
        if vpath:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self); self._audio.setVolume(0.6)
            self._player.setAudioOutput(self._audio)
            vw = QVideoWidget(); vw.setAspectRatioMode(Qt.KeepAspectRatio)
            self._player.setVideoOutput(vw); self._vwidget = vw
            self._vh_lo.addWidget(vw)
            self._player.setLoops(QMediaPlayer.Infinite)
            self._player.setSource(QUrl.fromLocalFile(vpath))
            self._player.play()
            self._media.setCurrentIndex(1)
            return
        ppath = _PA.inheritor_photo(it.get("photo", ""))
        if ppath and os.path.exists(ppath):
            self._pic.setPixmap(QPixmap(ppath).scaled(560, 420, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._pic.setStyleSheet("background:rgba(0,0,0,0.06);border-radius:8px;")
        else:
            self._pic.setPixmap(QPixmap())
            self._pic.setText("暂无素材")
            self._pic.setStyleSheet("background:rgba(0,0,0,0.06);border-radius:8px;font-size:16px;color:#888;")
        self._media.setCurrentIndex(0)

    def _update(self):
        if not INHERITORS:
            self._load_media(); return
        it = INHERITORS[self._index]
        self._name_label.setText(it.get("name", ""))
        self._body_label.setText("【%s】\n\n%s" % (it.get("project", ""), it.get("bio", "")))
        self._load_media()
