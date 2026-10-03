"""屏幕下方居中的操作提示（"✔ 已执行：xxx"）

**为什么从右上角搬下来**

摄像头悬浮窗只有 320×240，还缩在角落；而访客做完手势时**视线在屏幕正中**。
反馈出现在右上角那行小字里，他很可能根本没看见 —— 只觉得"我动了一下手，
然后画面变了"。搬到屏幕下方居中、再加淡入 + 上浮，"系统真的收到并执行了"
这件事才变得明确。

**它只负责显示**：什么时候弹、弹什么，由 `main_window` 的闸门决定。
动画必须绑在"**真的执行了动作**"上 —— 误触发配一个明显的成功动画，
看起来不是"灵敏"而是"坏了"。

**为什么自绘而不用子控件 + QGraphicsOpacityEffect**

透明度要整体作用在"圆角底 + 文字"上。用 `QGraphicsOpacityEffect` 也能做，
但那是图形效果链，在**纯 CPU** 展台上不划算。自绘一个几十像素的小胶囊
几乎不花什么，而且透明度完全由自己控制、没有平台差异。

**注意**：`paintEvent` 里所有颜色都乘上 `_opacity`。子控件不吃父控件的绘制，
所以这里**刻意不放子控件** —— 放了的话文字不会跟着淡出。
"""

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPropertyAnimation,
                            QRectF, Qt, QTimer)
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from src import config

FADE_IN_MS = 160        # 淡入
FADE_OUT_MS = 240       # 淡出
RISE_PX = 14            # 上浮距离：从下方 14px 升起
BOTTOM_MARGIN = 28      # 距窗口底边
PAD_X, PAD_Y = 28, 13   # 胶囊内边距

_FONT = lambda: QFont("Microsoft YaHei", 15, QFont.Bold)   # noqa: E731

_BG = (20, 40, 60)          # 深蓝底
_BORDER = (255, 200, 90)    # 金边
_TEXT = (255, 212, 121)     # 金字

_BG_ALPHA = 215
_BORDER_ALPHA = 225
_TEXT_ALPHA = 255


class ToastOverlay(QWidget):
    """一个自己管生死的胶囊提示。父窗口要做的只有两件：

      * 收到动作时调 `show_toast(text)`
      * 在自己的 `resizeEvent` 里调 `place()`
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 提示飘在页面之上，绝不能挡住鼠标 —— 否则底下的按钮就点不到了
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._text = ""
        self._font = _FONT()
        self._opacity = 0.0
        self._base = QPoint(0, 0)

        self._fade = QPropertyAnimation(self, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.InOutQuad)
        self._rise = QPropertyAnimation(self, b"pos", self)
        self._rise.setEasingCurve(QEasingCurve.OutCubic)

        # 停留计时；到点开始淡出
        self._hold = QTimer(self)
        self._hold.setSingleShot(True)
        self._hold.timeout.connect(self._fade_out)

        self.hide()

    # ---- 透明度：自己实现的 Qt 属性，供 QPropertyAnimation 驱动 ----
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float):
        self._opacity = float(v)
        self.update()          # 只重绘这个小胶囊，很便宜

    opacity = Property(float, _get_opacity, _set_opacity)

    # ---- 对外 ----
    def show_toast(self, text: str):
        self._text = text
        self._fit()
        self.place()
        self.show()
        self.raise_()          # 盖在页面和摄像头悬浮窗之上
        self._fade_to(1.0, FADE_IN_MS, start=0.0)
        self._slide(RISE_PX, 0, FADE_IN_MS)
        self._hold.start(config.TOAST_MS)

    def place(self):
        """贴到父窗口底部正中。父窗口 resize 时必须调一次。"""
        p = self.parentWidget()
        if p is None:
            return
        x = max(0, (p.width() - self.width()) // 2)
        y = max(0, p.height() - self.height() - BOTTOM_MARGIN)
        self._base = QPoint(x, y)
        if self.isVisible():
            self.move(self._base)

    def current_text(self) -> str:
        """当前显示的内容（测试用；正常只由 show_toast 写）"""
        return self._text

    # ---- 内部 ----
    def _fit(self):
        """按文字量出胶囊大小（没有子控件，所以得自己算）"""
        fm = QFontMetrics(self._font)
        self.resize(fm.horizontalAdvance(self._text) + 2 * PAD_X,
                    fm.height() + 2 * PAD_Y)

    def _fade_to(self, end: float, ms: int, start: float = None):
        self._fade.stop()
        self._fade.setDuration(ms)
        self._fade.setStartValue(self._opacity if start is None else start)
        self._fade.setEndValue(end)
        self._fade.start()

    def _slide(self, from_px: int, to_px: int, ms: int):
        self._rise.stop()
        self._rise.setDuration(ms)
        self._rise.setStartValue(self._base + QPoint(0, from_px))
        self._rise.setEndValue(self._base + QPoint(0, to_px))
        self._rise.start()

    def _fade_out(self):
        self._fade_to(0.0, FADE_OUT_MS)
        # 淡出结束才真正 hide()：否则会"啪"地消失，没有透明度过渡
        QTimer.singleShot(FADE_OUT_MS, self._hide_if_faded)

    def _hide_if_faded(self):
        """淡出结束后收尾。

        ⚠ 要再确认一次透明度：淡出期间可能又来了新动作（`show_toast` 把它拉回 1.0），
        那就不能把新提示一起藏掉。
        """
        if self._opacity <= 0.02:
            self.hide()

    # ---- 绘制 ----
    def paintEvent(self, event):
        if self._opacity <= 0.01:
            return
        k = self._opacity
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)   # 给 2px 边线留位
        radius = r.height() / 2.0
        p.setBrush(QColor(*_BG, int(_BG_ALPHA * k)))
        p.setPen(QPen(QColor(*_BORDER, int(_BORDER_ALPHA * k)), 2))
        p.drawRoundedRect(r, radius, radius)
        p.setPen(QColor(*_TEXT, int(_TEXT_ALPHA * k)))
        p.setFont(self._font)
        p.drawText(self.rect(), Qt.AlignCenter, self._text)
