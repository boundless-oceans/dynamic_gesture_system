"""换页过渡：在页面之上盖一层"上一页的快照"，再让它淡出

原先换页是**硬切**——画面瞬间一跳。加这一层之后就有了连续性。

**为什么用快照，而不是让两个页面各做淡入淡出**

  * `QStackedWidget` 一次只显示一个页面，没有"两层同时可见"这回事
  * 快照不碰页面控件本身：不重设父窗口、不与布局打架
    （首页卡片那套 `setFixedSize` + `QHBoxLayout` 就吃过这个亏）

**旧页面已经隐藏了还能截图吗** —— 能。`QWidget.grab()` 走的是 `render()`，
与可见性无关，而 `QStackedWidget` 隐藏非当前页时几何仍然保留。
（实测验证过：切页后对旧页面 `grab()`，拿到的仍是它自己那一页的内容。）

**⚠ 最容易坏的地方**：淡出结束后必须**真的 `hide()`**。
这个覆盖层是一整张**不透明的快照**，一旦卡住不消失，整个界面看起来就是
"死机"——而且不报任何错。所以单独写了用例守它。
"""

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QPainter
from PySide6.QtWidgets import QWidget

from src import config


class PageFade(QWidget):
    """换页过渡层。父窗口要做的只有两件：

      * 在换页时调 `start(旧页面的快照)`
      * 建在**页面容器**里（不是主窗口上），这样它只盖住页面，
        不会盖住右上角的摄像头悬浮窗
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # 过渡期间点击要能落到**新页面**上 —— 挡住鼠标会让人以为界面卡了
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self._snapshot = None
        self._opacity = 0.0

        self._anim = QPropertyAnimation(self, b"opacity", self)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.finished.connect(self._finish)

        self.hide()

    # ---- 透明度：自己实现的 Qt 属性，供 QPropertyAnimation 驱动 ----
    def _get_opacity(self) -> float:
        return self._opacity

    def _set_opacity(self, v: float):
        self._opacity = float(v)
        self.update()

    opacity = Property(float, _get_opacity, _set_opacity)

    # ---- 对外 ----
    def start(self, snapshot, duration_ms: int = None):
        """盖上快照并淡出。`snapshot` 为空、或时长为 0 时什么都不做（保持硬切）。"""
        duration = config.PAGE_FADE_MS if duration_ms is None else duration_ms
        if snapshot is None or snapshot.isNull() or duration <= 0:
            return
        p = self.parentWidget()
        if p is not None:
            self.setGeometry(p.rect())
        self._snapshot = snapshot
        self._opacity = 1.0
        self.show()
        self.raise_()
        self._anim.stop()          # stop() 不会发 finished，所以不会误清状态
        self._anim.setDuration(duration)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.start()

    def is_fading(self) -> bool:
        return self.isVisible()

    # ---- 内部 ----
    def _finish(self):
        self._snapshot = None
        self._opacity = 0.0
        self.hide()

    def paintEvent(self, event):
        if self._snapshot is None or self._opacity <= 0.01:
            return
        p = QPainter(self)
        p.setOpacity(self._opacity)
        p.drawPixmap(0, 0, self._snapshot)
