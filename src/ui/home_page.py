"""首页：两排卡片 —— 第一排非遗项目，第二排非遗传承人

**为什么是两排**：传承人入口原先挂在最右那个 `>` 按钮里（"向右抛到头就进传承人页"），
既不好发现、也点不准。改成第二排之后，一眼能看到全部传承人，而且删掉了那两个箭头。

**为什么每排几张不写死**：`per_row = max(项目数, 传承人数)`。
两排因此始终对齐、永远只有两排；以后加减项目**一行代码都不用改**。

**导航**（对应设置页手势表的「首页」列）：

    左 / 右   在**全部卡片的扁平顺序**上走一格，首尾环绕
              （第一排最右 → 第二排第一个；第二排最后 → 第一排第一个）
    上 / 下   跨排，也就是 ± 第一排的长度；对位不存在就不动
    单击      激活选中项：项目卡 → 详情页，传承人卡 → 传承人页**那一位**

**响应式**：卡片尺寸由窗口尺寸算出（不是固定值），字号、图片、印章都跟着缩放 ——
固定尺寸放到大屏幕上会显得很空。

⚠ **图片只在"算出来的尺寸真的变了"时才重新缩放**（`_ItemCard.refit` 里有缓存），
不能每次 resize 都缩 —— 而且原图只在构造时读一次磁盘，缩放都从内存里的原图来。

**没有用布局**：所有控件都是自己算坐标摆的。卡片尺寸每次窗口变化都要重算，
用布局的话会和"设死尺寸"互相打架（`setFixedSize` + `QHBoxLayout` 是这个项目踩过的坑）。
"""

import os
import time

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, QRectF, Qt,
                            QTimer, Signal)
from PySide6.QtGui import (QColor, QFont, QLinearGradient, QPainter, QPainterPath,
                           QPixmap)
from PySide6.QtWidgets import QGraphicsDropShadowEffect

from src.ui.base_page import BasePage
from src.core.project_data import PROJECTS, INHERITORS
from src.core import project_assets as _PA
from src import config

# 卡片的两种外观。选中态的边框加粗变橙 —— 与加呼吸/光条之前的视觉语言一致。
_FROSTED = ("QFrame { background: rgba(255,255,255,0.25); border: 1px solid rgba(255,255,255,0.5);"
            " border-radius: 16px; }"
            " QFrame:hover { background: rgba(255,255,255,0.55); border: 2px solid #ff9900; }")
_SELECTED = ("QFrame { background: rgba(255,255,255,0.5); border: 3px solid #ff7700;"
             " border-radius: 18px; }")

# 选中卡上那道光条（"光条流动"）。只是个装饰，参数都往克制里调 —— 别盖住卡片文字。
SHEEN_REFRESH_MS = 40          # 重绘间隔（25fps；它动得慢，够了）
SHEEN_SWEEP_FRAC = 0.34        # 一次扫过占整个周期的比例，其余时间是停顿
SHEEN_BAND_FRAC = 0.34         # 光条宽度占卡宽的比例
SHEEN_ALPHA = 70               # 最亮处的不透明度
SHEEN_RADIUS = 18              # 与选中态那个圆角一致（超出圆角的光会被裁掉）


def sheen_progress(t_ms: float):
    """光条此刻扫到卡宽的哪个位置（0~1）；**停顿期间返回 `None`（这一帧不用画）**。

    做成纯函数是好测：动效本身没法断言，但"它按周期扫、扫完停一段、关掉就完全不画"
    这几件事可以 —— 直接喂时间戳即可，不用起界面也不用等。
    """
    if not config.HOME_CARD_SHEEN:
        return None
    period = config.HOME_CARD_SHEEN_MS
    if period <= 0:
        return None
    phase = (t_ms % period) / float(period)
    if phase >= SHEEN_SWEEP_FRAC:
        return None
    return phase / SHEEN_SWEEP_FRAC


class _ItemCard(QFrame):
    """一张卡。项目卡和传承人卡共用 —— 区别只是有没有缩略图、有没有副标题。

    `index` 是**扁平索引**（全部卡片里的第几张），不是项目/传承人各自的下标 ——
    映射关系由 `HomePage._kinds` 持有。
    """

    clicked = Signal(int)
    double_clicked = Signal(int)

    def __init__(self, index: int, title: str, subtitle: str = "", image_path: str = "",
                 parent=None):
        # ⚠ parent 必须传。原先这张卡是被加进 QHBoxLayout 才成为子控件的；
        #    改成手工摆位之后如果忘了传 parent，它会变成一个**独立的顶层窗口**：
        #    move() 照样生效、x()/width() 照样有值，但**屏幕上什么都看不到**。
        super().__init__(parent)
        self.index = index
        self._selected = False
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(_FROSTED)

        # 原图只在构造时读一次；之后所有缩放都从内存里的它来。
        # （传承人目前**没有照片** —— photo 字段为空、assets/images/inheritors/ 不存在，
        #   所以第二排现在是纯文字卡。文化馆照片到位后这里自动就有图了。）
        self._src = None
        if image_path and os.path.exists(image_path):
            pm = QPixmap(image_path)
            if not pm.isNull():
                self._src = pm

        lay = QVBoxLayout(self)
        self._lay = lay
        self._img = QLabel()
        self._img.setAlignment(Qt.AlignCenter)
        self._title = QLabel(title)
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setWordWrap(True)
        self._sub = QLabel(subtitle)
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setVisible(bool(subtitle))
        self._title.setStyleSheet("background: transparent; border: none;")
        self._sub.setStyleSheet("background: transparent; border: none; color: #345;")
        self._img.setStyleSheet("background: rgba(255,255,255,0.3); border-radius: 10px;")

        if self._src is not None:
            lay.addWidget(self._img, 1)
        else:
            # 纯文字卡：上下各留一段弹性，把文字挤到竖直居中，别堆在顶上显得空
            lay.addStretch(1)
        lay.addWidget(self._title)
        if subtitle:
            lay.addWidget(self._sub)
        if self._src is None:
            lay.addStretch(1)

        self._refit_done = None
        # 尺寸 = 基准尺寸 × sel_scale。选中与否只改 sel_scale，
        # 于是"变大/缩小"可以做成一段动画（见 set_geometry_scale）。
        self._base_w, self._base_h = 160.0, 250.0
        self._scale = 1.0
        self._cx = self._cy = 0.0
        self._anim = QPropertyAnimation(self, b"sel_scale", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._apply_size()

    # ---- 尺寸 ----
    def _get_scale(self) -> float:
        return self._scale

    def _set_scale(self, v: float):
        self._scale = float(v)
        self._apply_size()

    sel_scale = Property(float, _get_scale, _set_scale)

    def place_at(self, cx: float, cy: float):
        """按**中心点**摆放。

        ⚠ 不能按左上角摆 —— 卡片尺寸在动画过程中一直在变，按左上角对齐的话
        它会"往右下角长"，看着像在爬。按中心对齐才是围绕自己变大。
        """
        self._cx, self._cy = float(cx), float(cy)
        self._move_to_center()

    def _move_to_center(self):
        self.move(int(round(self._cx - self.width() / 2.0)),
                  int(round(self._cy - self.height() / 2.0)))

    def set_geometry_scale(self, scale: float, base_w: float, base_h: float,
                           animate: bool = True):
        """给定基准尺寸和缩放比；`animate` 为真且缩放比变了就平滑过渡。

        窗口 resize（基准尺寸变了）**不做动画** —— 否则拖窗口时每张卡都在动。
        """
        base_changed = (int(base_w), int(base_h)) != (int(self._base_w), int(self._base_h))
        self._base_w, self._base_h = float(base_w), float(base_h)
        if base_changed:
            self._refit_done = None          # 基准变了 → 必须重排（哪怕缩放比没变）

        if (animate and not base_changed and config.HOME_SELECT_ANIM_MS > 0
                and abs(scale - self._scale) > 1e-6):
            self._anim.stop()
            self._anim.setDuration(config.HOME_SELECT_ANIM_MS)
            self._anim.setStartValue(self._scale)
            self._anim.setEndValue(float(scale))
            self._anim.start()
        else:
            self._anim.stop()
            self._set_scale(scale)           # 内含 _apply_size()

    def _apply_size(self):
        """按当前 `_base_*` 与 `_scale` 算出实际尺寸并重排。

        ⚠ 尺寸没变就直接返回。窗口 resize 时所有卡都会各调一次，
        而且动画期间每帧都会调 —— 每次都重新 scale 一遍大图会很卡。
        """
        w = max(48, int(round(self._base_w * self._scale)))
        h = max(72, int(round(self._base_h * self._scale)))
        if self._refit_done == (w, h):
            return
        self._refit_done = (w, h)

        self.setFixedSize(w, h)
        self._move_to_center()
        pad = max(4, int(w * 0.05))
        self._lay.setContentsMargins(pad, pad, pad, max(3, int(pad * 0.7)))
        self._lay.setSpacing(max(2, int(h * 0.012)))

        if self._src is not None:
            iw = max(16, w - 2 * pad)
            ih = max(16, int(h * 0.62) - 2 * pad)
            self._img.setFixedHeight(ih)
            self._img.setPixmap(self._src.scaled(iw, ih, Qt.KeepAspectRatio,
                                                 Qt.SmoothTransformation))

        self._apply_fonts(w)

    def _apply_fonts(self, w: int):
        # 用 setPixelSize 而不是点值：响应式布局里像素更可控
        f = QFont("Microsoft YaHei")
        # 字号跟卡宽走 —— 纯文字卡没有图，字放大一点才不显得空
        px = w * (0.20 if self._src is None else 0.115)
        f.setPixelSize(max(13, min(52, int(px))))
        f.setBold(True)
        self._title.setFont(f)

        if self._sub.text():
            sf = QFont("Microsoft YaHei")
            sf.setPixelSize(max(11, int(f.pixelSize() * 0.62)))
            self._sub.setFont(sf)

    def set_selected(self, s: bool):
        """只管外观；**尺寸由 HomePage 统一给**（它才知道整排的预算）"""
        if s == self._selected:
            return
        self._selected = s
        self.setStyleSheet(_SELECTED if s else _FROSTED)

    # ---- 鼠标 ----
    def mousePressEvent(self, e):
        self.clicked.emit(self.index)

    def mouseDoubleClickEvent(self, e):
        self.double_clicked.emit(self.index)

    # ---- 选中卡上的光条 ----
    def paintEvent(self, event):
        super().paintEvent(event)          # 先让 QSS 把毛玻璃底画出来
        if not self._selected:
            return
        p = sheen_progress(time.time() * 1000.0)
        if p is None:
            return                          # 停顿期（或关掉了这个效果）
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        band = max(24.0, w * SHEEN_BAND_FRAC)
        # 从卡外左侧扫到卡外右侧 —— 起步与收尾都在画面之外，所以看不出"突然出现/消失"
        x = -band + p * (w + 2 * band)
        g = QLinearGradient(x, 0.0, x + band, float(h))
        g.setColorAt(0.0, QColor(255, 255, 255, 0))
        g.setColorAt(0.5, QColor(255, 255, 255, SHEEN_ALPHA))
        g.setColorAt(1.0, QColor(255, 255, 255, 0))

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 裁进圆角里，否则光条会糊到卡片外面（圆角那四个角）
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), SHEEN_RADIUS, SHEEN_RADIUS)
        painter.setClipPath(path)
        painter.fillRect(self.rect(), g)


class HomePage(BasePage):
    item_selected = Signal(int)         # 项目下标 → 进详情页
    inheritor_selected = Signal(int)    # 传承人下标 → 进传承人页那一位

    def __init__(self):
        super().__init__()
        self.setAttribute(Qt.WA_StyledBackground, False)
        self._ready = False
        self._current = 0
        self._cards: list[_ItemCard] = []
        self._kinds: list[tuple] = []       # 与 _cards 对齐：(kind, 各自的下标)

        self._title = QLabel("庐州非遗", self)
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet("background: transparent; color: #1a3a5c;")
        glow = QGraphicsDropShadowEffect()
        glow.setBlurRadius(20)
        glow.setColor(QColor(200, 160, 60, 200))
        glow.setOffset(0, 0)
        self._title.setGraphicsEffect(glow)

        self._seal = QLabel("非遗\n珍宝", self)
        self._seal.setAlignment(Qt.AlignCenter)
        self._seal.setStyleSheet("color:white;background:rgba(180,40,40,0.65);"
                                 "border:3px solid rgba(140,30,30,0.6);border-radius:8px;")

        self._build_cards()

        # 光条的刷新定时器。**只重绘选中那一张**，而且只在页面可见时跑 ——
        # 展台 24 小时开着，没人看的时候不该烧 CPU 重绘。
        self._sheen = QTimer(self)
        self._sheen.setInterval(SHEEN_REFRESH_MS)
        self._sheen.timeout.connect(self._tick_sheen)
        self._sheen_live = False        # 上一帧是否真的画了光条（用于收尾那一帧）

        self._ready = True
        self._update()

    # ---- 光条的驱动 ----
    def _tick_sheen(self):
        if not self._cards:
            return
        if sheen_progress(time.time() * 1000.0) is None:
            # 停顿期：不重绘。但**扫完要补刷一帧**，否则最后一帧可能停在
            # 光条刚探进卡里的位置上，留下一条淡淡的竖边。
            if self._sheen_live:
                self._sheen_live = False
                self._cards[self._current].update()
            return
        self._sheen_live = True
        self._cards[self._current].update()

    def showEvent(self, e):
        super().showEvent(e)
        if config.HOME_CARD_SHEEN:
            self._sheen.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self._sheen.stop()

    # ---- 卡片 ----
    def _build_cards(self):
        # 第一排：非遗项目（图来自 assets/images/<slug>/thumb.jpg）
        for i, p in enumerate(PROJECTS):
            self._add_card("project", i, p.get("name", ""), "", _PA.thumb_path(i))
        # 第二排：非遗传承人（照片目前是空的 → 纯文字卡）
        for j, it in enumerate(INHERITORS):
            self._add_card("inheritor", j, it.get("name", ""), it.get("project", ""),
                           _PA.inheritor_photo(it.get("photo", "")))

    def _add_card(self, kind: str, index: int, title: str, subtitle: str, image_path: str):
        flat = len(self._cards)
        c = _ItemCard(flat, title, subtitle, image_path, parent=self)
        c.clicked.connect(self._on_click_flat)        # 单击 = 只选中
        c.double_clicked.connect(self._on_double_flat)  # 双击 = 激活
        self._cards.append(c)
        self._kinds.append((kind, index))

    # ---- 每排几张 ----
    @property
    def _row1(self) -> int:
        """第一排（项目）的长度。上下跨排就是 ± 它。"""
        return len(PROJECTS)

    @property
    def _per_row(self) -> int:
        """每排几张。取两排里长的那个 —— 这样两排始终对齐、永远只有两排。

        **刻意不写死 8**：用户说了"不排除甲方变卦"，加减项目不应该要改代码。
        """
        return max(self._row1, len(INHERITORS), 1)

    def current_kind(self) -> str:
        if not self._kinds:
            return ""
        return self._kinds[self._current][0]

    def current_target(self) -> tuple:
        """当前选中的是"哪一个"：`("project", i)` 或 `("inheritor", j)`。

        ⚠ 与 `current_index()` 不是一回事：那个是**扁平**索引（全部卡片里的第几张），
        这个是**各自那一排里**的下标。点赞要按后者算，因为它才是"这是哪个项目/哪个人"。
        """
        if not self._kinds:
            return ("", -1)
        return self._kinds[self._current]

    def current_index(self) -> int:
        """当前选中的**扁平索引**（全部卡片里的第几张）"""
        return self._current

    def current_item(self) -> str:
        if not self._cards:
            return ""
        return self._cards[self._current]._title.text()

    def card_count(self) -> int:
        return len(self._cards)

    # ---- 导航 ----
    def _move(self, i: int):
        n = len(self._cards)
        if n == 0:
            return
        self._current = i % n          # 环绕
        self._update(animate=True)     # 选中变化 → "变大/缩小"走缓动

    def _prev(self):
        """向左：扁平顺序上一张（第一张再向左 → 最后一张）"""
        self._move(self._current - 1)

    def _next(self):
        """向右：扁平顺序下一张（最后一张再向右 → 第一张）"""
        self._move(self._current + 1)

    def _up(self):
        """向上：换到上一排。已在第一排就不动。"""
        if self._current >= self._row1:
            self._move(self._current - self._row1)

    def _down(self):
        """向下：换到下一排。对位不存在（排长不齐）就不动。"""
        t = self._current + self._row1
        if self._current < self._row1 and t < len(self._cards):
            self._move(t)

    # ---- 点击 ----
    def _on_click_flat(self, flat: int):
        self._current = flat % max(1, len(self._cards))
        self._update(animate=True)

    def _on_double_flat(self, flat: int):
        self._on_click_flat(flat)
        self.activate_current()

    def activate_current(self):
        """激活当前选中项（手势"单击"走这里）。

        项目卡 → 进详情页；传承人卡 → 进传承人页**那一位**。
        """
        if not self._kinds:
            return
        kind, index = self._kinds[self._current]
        if kind == "project":
            self.item_selected.emit(index)
        else:
            self.inheritor_selected.emit(index)

    # ---- 布局 ----
    def _update(self, animate: bool = False):
        """`animate=True` 只在**选中变化**时用；窗口 resize 一律不做动画
        （否则拖窗口时每张卡都在动）。"""
        self._relayout(animate=animate)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self, animate: bool = False):
        if not self._ready:
            return
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        self._layout_title_and_seal(w, h)
        self._layout_cards(w, h, animate)

    def _layout_title_and_seal(self, w: int, h: int):
        f = QFont("STKaiti")
        f.setPixelSize(max(28, min(110, int(w * 0.038))))
        f.setBold(True)
        self._title.setFont(f)
        self._title.adjustSize()
        self._title.move(max(0, (w - self._title.width()) // 2), max(4, int(h * 0.012)))

        seal = max(70, min(240, int(w * 0.10)))
        self._seal.setFixedSize(seal, seal)
        sf = QFont("STKaiti")
        sf.setPixelSize(max(16, int(seal * 0.24)))
        sf.setBold(True)
        self._seal.setFont(sf)
        self._seal.move(max(10, int(w * 0.018)), max(10, int(h * 0.028)))

    def _layout_cards(self, w: int, h: int, animate: bool = False):
        n = len(self._cards)
        if n == 0:
            return
        per = self._per_row
        # 卡片区上边界要让开右上角的摄像头悬浮窗，下边界要让开那两个全局按钮
        top = config.HOME_TOP_RESERVE_PX
        avail_h = max(80, h - config.HOME_BOTTOM_RESERVE_PX - top)
        gap = max(6, int(w * 0.008))
        side = max(8, int(w * 0.014))
        avail_w = max(120, w - 2 * side)

        # ⚠ 总宽预算是按"选中后"算的：base * per_row * SCALE + 间隙 <= 可用宽。
        #   所以选中哪一张，整排都不会被顶得位移（代价是平常每张略小一点点）。
        base_w = (avail_w - (per - 1) * gap) / (per * config.HOME_SELECTED_SCALE)
        base_h = base_w / config.HOME_CARD_ASPECT
        if 2 * base_h + gap > avail_h:            # 高度装不下 → 按高度反推宽度
            base_h = (avail_h - gap) / 2.0
            base_w = base_h * config.HOME_CARD_ASPECT
        base_w = max(48, int(base_w))
        base_h = max(72, int(base_h))
        scale = config.HOME_SELECTED_SCALE

        row_w = per * base_w + (per - 1) * gap
        x0 = max(0, (w - row_w) // 2)
        block_h = 2 * base_h + gap
        y0 = top + max(0, (avail_h - block_h) // 2)

        for i, card in enumerate(self._cards):
            row, col = divmod(i, per)
            sel = (i == self._current)
            card.set_selected(sel)
            # ⚠ 按**槽位的中心点**摆，不是左上角 —— 卡片在动画里尺寸一直在变，
            #   按左上角对齐会让它"往右下角长"。按中心对齐才是围绕自己变大，
            #   而多出来的那几像素正好落进槽位间隙里，不会碰到邻居。
            card.place_at(x0 + col * (base_w + gap) + base_w / 2.0,
                          y0 + row * (base_h + gap) + base_h / 2.0)
            card.set_geometry_scale(scale if sel else 1.0, base_w, base_h,
                                    animate=animate)
