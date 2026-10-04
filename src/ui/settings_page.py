"""设置页：手势说明 / 现场调参 / 图片来源"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMessageBox, QPushButton, QSlider,
    QTableWidget, QTableWidgetItem, QHeaderView, QTabWidget, QFrame, QScrollArea,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QPainter, QLinearGradient, QColor

from src import config

# 手势对照表。
# ⚠ 真值来源是 main_window.MainWindow._ocg 的分发逻辑，改手势映射时必须同步这里。
#   历史教训：这张表曾长期列着 palm（映射代码里根本不会产出该手势，回首页已改用按钮），
#   也把详情页的"选中左移/右移"错写成"上下滚动"，会误导使用者。
_HEADERS = ["手势", "首页", "详情页", "传承人", "3D 展示"]
_ROWS = [
    ("向左抛出", "上一项",   "左移选中",  "快退 30 秒", "—"),
    ("向右抛出", "下一项",   "右移选中",  "快进 30 秒", "—"),
    ("向上抛出", "上一排",   "—",        "上一位",     "—"),
    ("向下抛出", "下一排",   "—",        "下一位",     "—"),
    ("单击",     "进入选中项", "执行选中项", "返回首页",   "返回详情"),
    ("张开两次", "—",        "—",        "—",         "放大"),
    ("握拳缩小", "—",        "—",        "—",         "缩小"),
    ("双指指向", "—",        "—",        "—",         "旋转模型"),
    ("双指双击", "—",        "—",        "—",         "旋转模型"),
]

# 静态手势（HaGRID 34 类 ResNet18）对照表。
# ⚠ 这两个**基本上不跟页面走** —— 任何页面上都生效，所以单独一张表，不塞进上面
#   那张按页面分列的表里（塞进去只能给每一列都填同一个动作，读起来更乱）。
#   唯一的例外是「比耶」在 3D 页要让位，见下面的脚注。
# 只绑这两个的理由见 gesture_mapper.STATIC_TO_CONTROL：其余静态类的手型都与
# **在用的动态手势**撞车（张开手掌撞"张开两次"、握拳撞"缩小"、食指撞"单击"、
# 两指撞"双指指向"），而两个模型吃的是同一块画面，会同时被同一只手点燃。
_STATIC_HEADERS = ["手势", "动作"]
_STATIC_ROWS = [
    ("OK 手势", "返回首页"),
    ("比耶",    "进入手势说明页"),
    ("点赞",    "给当前项目 / 传承人点赞"),
]

_FOOTNOTES = [
    "详情页的「非遗详情」子页：向左/向右变为视频快退/快进，单击返回主视图。",
    "上表中未列出的动态手势（单指指向、双击、双指点击）不触发任何操作；"
    "实测偏弱或易混的类别刻意不绑定，被误判也不会产生动作。",
    "「旋转模型」同时接受「双指指向」与「双指双击」：模型对这两个「双指」类分不太开"
    "（慢速的双指指向常被认成双指双击），而两者访客意图相同，故合并到同一个动作。",
    "静态手势「比耶」在 3D 展示页不生效：那一页的「两指」是「旋转模型」的手势，"
    "两者是同一个手型，为避免一只手被两边同时认走，那一页优先给动态模型。",
    "鼠标点击按钮始终可用，摄像头关闭时整套界面仍能正常操作。",
]

# 图片来源 / 开源组件署名（CC BY-SA 3.0 要求保留署名与许可信息，故在应用内可见）
_CREDITS_HTML = """
<style>
  h3 {{ margin: 14px 0 4px 0; color: #2c5f7c; }}
  p  {{ margin: 2px 0 10px 0; }}
  a  {{ color: #1a6fa8; }}
</style>
<h3>外部素材（自由授权）</h3>
<p><b>合肥包公祠内包拯像</b>（用于「包公故事」轮播图）<br/>
作者：猫猫的日记本（Wikimedia Commons 用户）<br/>
来源：<a href="https://commons.wikimedia.org/wiki/File:The_Memorial_Temple_of_Bao_Zheng_in_Hefei_2012-06.JPG">
commons.wikimedia.org — The Memorial Temple of Bao Zheng in Hefei</a><br/>
授权：<a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a>
（<b>本页署名即为该许可要求的署名，请勿删除</b>）<br/>
修改：等比缩放到宽 1600px 后转存</p>

<p><b>刘铭传像</b>（用于「刘铭传故事」轮播图）<br/>
作者：不详（19 世纪原版照片，摄于 1896 年之前）<br/>
来源：<a href="https://commons.wikimedia.org/wiki/File:劉銘傳肖像.jpg">
commons.wikimedia.org — 劉銘傳肖像</a><br/>
授权：<b>公有领域</b>（Public domain，已过版权保护期，无强制署名要求）<br/>
说明：刘铭传（1836—1896），清末淮军名将、台湾首任巡抚</p>

<h3>文化馆提供素材（版权归原提供方）</h3>
<p>其余图片、二维码、3D 模型（由资料中的 FBX 转换）与介绍视频（由原始视频转码）
均来自文化馆项目资料，仅用于本展示系统。</p>

<h3>开源组件</h3>
<p>three.js（MIT）、GLTFLoader（MIT）、
PySide6（LGPL v3）、PyTorch（BSD-3-Clause）、OpenCV（Apache-2.0）。</p>
"""


def _flat_button(text, slot, w=130, h=40, pt=12) -> QPushButton:
    """设置页上那种白底圆角按钮。

    这一页原本把同一段样式抄了三遍（返回首页 / 保存为默认 / 清空点赞计数），
    字号和圆角还各差一点 —— 抽出来，改一次全都跟着变。
    """
    b = QPushButton(text)
    b.setFixedSize(w, h)
    b.setFont(QFont("Microsoft YaHei", pt))
    b.setStyleSheet(
        "QPushButton { background: rgba(255,255,255,0.85); border: 1px solid #aaa;"
        " border-radius: 8px; } QPushButton:hover { background: #fff; }")
    b.clicked.connect(slot)
    return b


def _build_table(headers, rows, row_h=36) -> QTableWidget:
    """按内容撑到刚好高的只读表格。手势说明那一页有两张（动态 / 静态），共用这个。

    ⚠ 高度必须**按行数算死**：QTableView 自身的 sizeHint 很小，
    交给布局拉伸会留一大片空白表体，不拉伸又会被压出滚动条并截断行。
    """
    table = QTableWidget()
    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(list(headers))
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.setSelectionMode(QTableWidget.NoSelection)
    table.setFont(QFont("Microsoft YaHei", 12))
    table.setRowCount(len(rows))
    table.verticalHeader().setDefaultSectionSize(row_h)
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            item = QTableWidgetItem(cell)
            item.setTextAlignment(Qt.AlignCenter)
            if j == 0:
                item.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
            table.setItem(i, j, item)
    table.setStyleSheet("""
        QTableWidget { background: rgba(255,255,255,0.5);
                       border-radius: 10px; gridline-color: #ddd; }
        QHeaderView::section { background: rgba(91,167,209,0.3);
                               font-weight: bold; padding: 8px; border: none; }
    """)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    table.setFixedHeight(max(table.horizontalHeader().height(), 34)
                         + len(rows) * row_h + 2)
    return table


class SettingsPage(QWidget):
    """手势操作说明 + 现场调参 + 图片来源"""

    go_home = Signal()
    likes_reset = Signal()      # 点赞清零之后发一下，主窗口拿去刷新首页角标

    def __init__(self):
        super().__init__()
        self._sliders = {}      # key -> (QSlider, QLabel 数值)
        self._likes = None      # 点赞存档，由主窗口给（见 set_like_store）
        self._setup_ui()

    def paintEvent(self, event):
        painter = QPainter(self)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(91, 167, 209))
        painter.fillRect(self.rect(), gradient)

    # ---------------- 页面骨架 ----------------
    def _setup_ui(self):
        self.setAttribute(Qt.WA_StyledBackground, False)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 24, 40, 24)
        layout.setSpacing(12)

        title = QLabel("手势说明与设置")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("STKaiti", 32, QFont.Bold))
        title.setStyleSheet("background: transparent;")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.setFont(QFont("Microsoft YaHei", 12))
        tabs.setStyleSheet("""
            QTabWidget::pane { background: rgba(255,255,255,0.55);
                               border: 1px solid rgba(255,255,255,0.7); border-radius: 10px; }
            QTabBar::tab { background: rgba(255,255,255,0.55); padding: 8px 22px;
                           margin-right: 4px; border-top-left-radius: 8px;
                           border-top-right-radius: 8px; }
            QTabBar::tab:selected { background: rgba(255,255,255,0.95); font-weight: bold; }
        """)
        tabs.addTab(self._tab_gestures(), "手势说明")
        tabs.addTab(self._tab_tuning(), "参数调节")
        tabs.addTab(self._tab_credits(), "图片来源")
        layout.addWidget(tabs, stretch=1)
        self._tabs = tabs

        nav = QHBoxLayout()
        nav.setAlignment(Qt.AlignCenter)
        nav.addWidget(_flat_button("返回首页", self.go_home.emit, 140, 44, 13))
        layout.addLayout(nav)

    def show_gestures(self):
        """切到「手势说明」那一栏。

        静态手势「比耶」进来时会先调这个 —— 否则操作员上次若停在「参数调节」，
        访客比个耶就会看到一屏滑条，莫名其妙。
        """
        self._tabs.setCurrentIndex(0)

    # ---------------- 标签页一：手势说明 ----------------
    def _tab_gestures(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(10)

        section = QLabel("动态手势（识别「手的动作」）")
        section.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        section.setStyleSheet("background: transparent; color: #2c5f7c;")
        lo.addWidget(section)
        lo.addWidget(_build_table(_HEADERS, _ROWS))

        # 静态手势单独一张表：它**不跟页面走**，任何页面上都生效
        section2 = QLabel("静态手势（识别「手此刻的形状」）· 任何页面都可用")
        section2.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        section2.setStyleSheet("background: transparent; color: #2c5f7c;")
        section2.setContentsMargins(0, 8, 0, 0)
        lo.addWidget(section2)
        lo.addWidget(_build_table(_STATIC_HEADERS, _STATIC_ROWS))

        for text in _FOOTNOTES:
            tip = QLabel("· " + text)
            tip.setWordWrap(True)
            tip.setFont(QFont("Microsoft YaHei", 10))
            tip.setStyleSheet("background: transparent; color: #555;")
            lo.addWidget(tip)

        tip = QLabel("提示：鼠标点击按钮作为兜底操作，摄像头关闭时仍可正常使用")
        tip.setAlignment(Qt.AlignCenter)
        tip.setFont(QFont("Microsoft YaHei", 11))
        tip.setStyleSheet("background: transparent; color: #333;")
        lo.addWidget(tip)
        lo.addStretch(1)          # 多余空间留在底部，而不是摊进表体
        return w

    # ---------------- 标签页二：现场调参 ----------------
    def _tab_tuning(self) -> QWidget:
        w = QWidget()
        outer = QVBoxLayout(w)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(10)

        head = QLabel("拖动滑条立即生效（无需重启）。改动默认只临时生效，"
                      "重启后回到上次保存的值——避免观众乱拖把展台参数改坏。")
        head.setWordWrap(True)
        head.setFont(QFont("Microsoft YaHei", 11))
        head.setStyleSheet("background: transparent; color: #333;")
        outer.addWidget(head)

        inner = QWidget()
        inner.setStyleSheet("background: transparent;")
        lo = QVBoxLayout(inner)
        lo.setContentsMargins(0, 0, 8, 0)
        lo.setSpacing(6)

        for spec in config.TUNABLE:
            lo.addLayout(self._param_row(spec))
        lo.addStretch()

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                         "QScrollArea > QWidget > QWidget{background:transparent;}")
        sa.setWidget(inner)
        outer.addWidget(sa, stretch=1)

        # 操作按钮 + 状态反馈
        row = QHBoxLayout()
        row.setAlignment(Qt.AlignCenter)
        row.setSpacing(16)
        for text, slot in (("保存为默认", self._on_save), ("恢复默认", self._on_reset)):
            row.addWidget(_flat_button(text, slot))
        outer.addLayout(row)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setFont(QFont("Microsoft YaHei", 11))
        self._status.setStyleSheet("background: transparent; color: #2c7a2c;")
        outer.addWidget(self._status)

        # ---- 点赞计数 ----
        # 它不是"参数"，是**运行时数据**；放在这一栏是因为这里是操作员的地盘，
        # 而且它和上面那两个按钮一样属于"会改掉长期状态"的操作。
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("border: none; border-top: 1px solid rgba(0,0,0,0.15);")
        outer.addWidget(sep)

        self._like_summary = QLabel("")
        self._like_summary.setAlignment(Qt.AlignCenter)
        self._like_summary.setFont(QFont("Microsoft YaHei", 11))
        self._like_summary.setStyleSheet("background: transparent; color: #333;")
        outer.addWidget(self._like_summary)

        like_row = QHBoxLayout()
        like_row.setAlignment(Qt.AlignCenter)
        self._like_btn = _flat_button("清空点赞计数", self._on_reset_likes, 150, 40)
        like_row.addWidget(self._like_btn)
        outer.addLayout(like_row)

        self._like_status = QLabel("")
        self._like_status.setAlignment(Qt.AlignCenter)
        self._like_status.setFont(QFont("Microsoft YaHei", 10))
        self._like_status.setStyleSheet("background: transparent; color: #b8860b;")
        outer.addWidget(self._like_status)
        return w

    def _param_row(self, spec: dict) -> QVBoxLayout:
        """一行参数：标签 + 滑条 + 当前值，下方跟一句说明"""
        box = QVBoxLayout()
        box.setSpacing(2)

        top = QHBoxLayout()
        top.setSpacing(12)
        name = QLabel(spec["label"])
        name.setFixedWidth(140)
        name.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        name.setStyleSheet("background: transparent;")
        top.addWidget(name)

        scale = 10 ** spec["decimals"]
        s = QSlider(Qt.Horizontal)
        s.setMinimum(int(spec["min"] * scale))
        s.setMaximum(int(spec["max"] * scale))
        s.setSingleStep(1)
        s.setPageStep(1)
        s.setValue(int(getattr(config, spec["key"]) * scale))
        top.addWidget(s, stretch=1)

        val = QLabel()
        val.setFixedWidth(90)
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        val.setFont(QFont("Consolas", 13, QFont.Bold))
        val.setStyleSheet("background: transparent; color: #1a6fa8;")
        top.addWidget(val)
        box.addLayout(top)

        hint = QLabel(spec["hint"])
        hint.setWordWrap(True)
        hint.setFont(QFont("Microsoft YaHei", 9))
        hint.setStyleSheet("background: transparent; color: #777;")
        hint.setContentsMargins(152, 0, 0, 6)
        box.addWidget(hint)

        def fmt(v: float) -> str:
            return f"{v:.{spec['decimals']}f}" + (" " + spec["unit"] if spec.get("unit") else "")

        def on_change(raw: int, key=spec["key"], scale=scale):
            v = round(raw / scale, spec["decimals"])
            if spec["decimals"] == 0:
                v = int(v)
            setattr(config, key, v)          # 运行期直接生效：main_window 每次都读 config.X
            self._sliders[key][1].setText(fmt(v))
            self._mark_dirty()

        # 先登记再连接：避免任何一次 valueChanged 早于 self._sliders 就绪
        self._sliders[spec["key"]] = (s, val)
        val.setText(fmt(getattr(config, spec["key"])))
        s.valueChanged.connect(on_change)
        return box

    # ---------------- 点赞计数 ----------------
    def set_like_store(self, store):
        """把点赞存档交给这一页读 / 清（主窗口给的）。"""
        self._likes = store
        self.refresh_like_summary()

    def refresh_like_summary(self):
        if self._likes is None or not hasattr(self, "_like_summary"):
            return
        d = self._likes.all_counts()
        if d:
            self._like_summary.setText(
                "点赞：已有 %d 项被赞过，共 %d 次（数字显示在首页卡片右上角）"
                % (len(d), sum(d.values())))
        else:
            self._like_summary.setText("点赞：还没有任何记录")

    def _confirm_box(self, title, text) -> QMessageBox:
        """搭出确认框（**只搭不弹**）。

        ⚠️ **必须显式给底色，不能用默认样式。** 主窗口在页面容器上设过
        `background: transparent`，而 **Qt 的样式表会传给子控件** ——
        QMessageBox 是这一页的子窗口，底色就跟着变成透明的，
        在 Windows 上直接渲染成**一片纯黑**（实测平均亮度 229 → 3.8），
        按钮在哪都看不见，操作员根本没法确认。

        拆成单独一个方法是为了**能测它的配色** —— 弹一个模态框会把用例挂死，
        但搭出来 `grab()` 一下不会。
        """
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)     # 默认落在"否"，别让回车误清
        # Qt 默认给的是英文 Yes/No（没装翻译）—— 换成说清楚要干什么的中文
        box.button(QMessageBox.Yes).setText("确定清空")
        box.button(QMessageBox.No).setText("取消")
        box.setStyleSheet(
            # 字体显式指定，与其余界面一致（别指望系统默认字体）
            "QMessageBox { background: #f4f4f4; }"
            'QMessageBox QLabel { color: #222; background: transparent;'
            ' font-family: "Microsoft YaHei"; font-size: 14px; }'
            'QMessageBox QPushButton { background: #ffffff; color: #222;'
            ' border: 1px solid #999; border-radius: 6px;'
            ' padding: 6px 20px; min-width: 72px;'
            ' font-family: "Microsoft YaHei"; font-size: 14px; }'
            "QMessageBox QPushButton:hover { background: #e6e6e6; }"
            "QMessageBox QPushButton:default { background: #dceaf5;"
            " border-color: #4a90c4; }")
        return box

    def _ask(self, title, text) -> bool:
        """弹确认框。做成**方法**是为了让用例能换掉它 ——
        模态框会把离屏测试**挂死**（Qt 等不到人点按钮）。"""
        box = self._confirm_box(title, text)
        try:
            return box.exec() == QMessageBox.Yes
        finally:
            box.deleteLater()

    def _on_reset_likes(self):
        """清空点赞计数。

        ⚠️ **必须先看一眼有多少、再确认** —— 这是清掉长期攒下来的数据，
        点错了没法撤销，而且没有任何地方能恢复。
        """
        if self._likes is None:
            # 宁可说一句，也别**点了没反应**（那种坏法没人查得出来）
            self._like_status.setText("没有接到点赞存档，这个按钮用不了")
            return
        d = self._likes.all_counts()
        if not d:
            self._like_status.setStyleSheet("background: transparent; color: #b8860b;")
            self._like_status.setText("还没有任何点赞，不用清")
            return
        if not self._ask("清空点赞计数",
                         "将清空全部 %d 项的点赞数（共 %d 次）。\n\n"
                         "清掉之后无法恢复，确定吗？" % (len(d), sum(d.values()))):
            return
        self._likes.reset()
        self.refresh_like_summary()
        self._like_status.setStyleSheet("background: transparent; color: #2c7a2c;")
        self._like_status.setText("✔ 点赞计数已清空")
        self.likes_reset.emit()

    def showEvent(self, e):
        super().showEvent(e)
        # 数字可能在别的页面上被改过（或者刚被清过），进来时重新算一遍
        self.refresh_like_summary()

    def _mark_dirty(self):
        self._status.setStyleSheet("background: transparent; color: #b8860b;")
        self._status.setText("当前为临时设置（重启后回到上次保存的值）")

    def _on_save(self):
        path = config.save_local_overrides()
        self._status.setStyleSheet("background: transparent; color: #2c7a2c;")
        self._status.setText(f"✔ 已保存为默认，重启后自动生效（{path}）")

    def _on_reset(self):
        config.reset_to_defaults()
        self._sync_sliders()
        self._status.setStyleSheet("background: transparent; color: #2c7a2c;")
        self._status.setText("✔ 已恢复代码默认值，并删除本地调参文件")

    def _sync_sliders(self):
        """把 config 当前值刷回滑条（屏蔽信号，避免触发 _mark_dirty）"""
        for spec in config.TUNABLE:
            s, val = self._sliders[spec["key"]]
            scale = 10 ** spec["decimals"]
            v = getattr(config, spec["key"])
            s.blockSignals(True)
            s.setValue(int(v * scale))
            s.blockSignals(False)
            val.setText(f"{v:.{spec['decimals']}f}"
                        + (" " + spec["unit"] if spec.get("unit") else ""))

    # ---------------- 标签页三：图片来源 ----------------
    def _tab_credits(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(16, 16, 16, 16)

        label = QLabel(_CREDITS_HTML)
        label.setWordWrap(True)
        label.setTextFormat(Qt.RichText)
        label.setOpenExternalLinks(True)     # 许可链接可点开
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        label.setFont(QFont("Microsoft YaHei", 11))
        label.setStyleSheet("background: transparent; color: #333;")
        label.setTextInteractionFlags(Qt.TextBrowserInteraction)

        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                         "QScrollArea > QWidget > QWidget{background:transparent;}")
        sa.setWidget(label)
        lo.addWidget(sa)
        return w
