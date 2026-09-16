"""设置页：手势说明 / 现场调参 / 图片来源"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
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
_HEADERS = ["手势", "首页", "详情页", "传承人", "3D 展示", "地图"]
_ROWS = [
    ("向左抛出", "上一项",   "左移选中",  "快退 30 秒", "—",       "左移"),
    ("向右抛出", "下一项",   "右移选中",  "快进 30 秒", "—",       "右移"),
    ("向上抛出", "—",        "—",        "上一位",     "—",       "上移"),
    ("向下抛出", "—",        "—",        "下一位",     "—",       "下移"),
    ("单击",     "进入详情", "执行选中项", "返回首页",   "返回详情", "返回首页"),
    ("张开两次", "—",        "—",        "—",         "放大",     "放大"),
    ("握拳缩小", "—",        "—",        "—",         "缩小",     "缩小"),
    ("双击",     "—",        "—",        "—",         "旋转模型", "—"),
]

_FOOTNOTES = [
    "详情页的「非遗详情」子页：向左/向右变为视频快退/快进，单击返回主视图。",
    "未列出的手势（单指指向、双指指向、双指点击、双指双击）不触发任何操作；"
    "实测偏弱或易混的类别刻意不绑定，被误判也不会产生动作。",
    "鼠标点击按钮始终可用，摄像头关闭时整套界面仍能正常操作。",
]

# 图片来源 / 开源组件署名（CC BY-SA 3.0 要求保留署名与许可信息，故在应用内可见）
_CREDITS_HTML = """
<style>
  h3 {{ margin: 14px 0 4px 0; color: #2c5f7c; }}
  p  {{ margin: 2px 0 10px 0; }}
  a  {{ color: #1a6fa8; }}
</style>
<h3>外部素材（自由授权，需保留署名）</h3>
<p><b>合肥包公祠内包拯像</b>（用于「包公故事」轮播图）<br/>
作者：猫猫的日记本（Wikimedia Commons 用户）<br/>
来源：<a href="https://commons.wikimedia.org/wiki/File:The_Memorial_Temple_of_Bao_Zheng_in_Hefei_2012-06.JPG">
commons.wikimedia.org — The Memorial Temple of Bao Zheng in Hefei</a><br/>
授权：<a href="https://creativecommons.org/licenses/by-sa/3.0">CC BY-SA 3.0</a><br/>
修改：等比缩放到宽 1600px 后转存</p>

<h3>文化馆提供素材（版权归原提供方）</h3>
<p>其余图片、二维码、3D 模型（由资料中的 FBX 转换）与介绍视频（由原始视频转码）
均来自文化馆项目资料，仅用于本展示系统。</p>

<h3>开源组件</h3>
<p>three.js（MIT）、GLTFLoader（MIT）、Leaflet（BSD-2-Clause）、
PySide6（LGPL v3）、PyTorch（BSD-3-Clause）、OpenCV（Apache-2.0）。<br/>
地图底图 © 高德地图（<a href="https://www.amap.com">amap.com</a>）。</p>
"""


class SettingsPage(QWidget):
    """手势操作说明 + 现场调参 + 图片来源"""

    go_home = Signal()

    def __init__(self):
        super().__init__()
        self._sliders = {}      # key -> (QSlider, QLabel 数值)
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

        nav = QHBoxLayout()
        nav.setAlignment(Qt.AlignCenter)
        btn_home = QPushButton("返回首页")
        btn_home.setFixedSize(140, 44)
        btn_home.setFont(QFont("Microsoft YaHei", 13))
        btn_home.setStyleSheet(
            "QPushButton { background: rgba(255,255,255,0.8); border: 1px solid #aaa;"
            " border-radius: 8px; } QPushButton:hover { background: rgba(255,255,255,1); }")
        btn_home.clicked.connect(self.go_home.emit)
        nav.addWidget(btn_home)
        layout.addLayout(nav)

    # ---------------- 标签页一：手势说明 ----------------
    def _tab_gestures(self) -> QWidget:
        w = QWidget()
        lo = QVBoxLayout(w)
        lo.setContentsMargins(16, 16, 16, 16)
        lo.setSpacing(10)

        table = QTableWidget()
        table.setColumnCount(len(_HEADERS))
        table.setHorizontalHeaderLabels(_HEADERS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFont(QFont("Microsoft YaHei", 12))
        table.setRowCount(len(_ROWS))
        ROW_H = 36
        table.verticalHeader().setDefaultSectionSize(ROW_H)
        for i, row in enumerate(_ROWS):
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
        # 高度按内容固定：QTableView 自身 sizeHint 很小，
        # 交给布局拉伸会留一大片空白表体，不拉伸又会被压出滚动条并截断行。
        table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        table.setFixedHeight(max(table.horizontalHeader().height(), 34)
                             + len(_ROWS) * ROW_H + 2)
        lo.addWidget(table)

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
            b = QPushButton(text)
            b.setFixedSize(130, 40)
            b.setFont(QFont("Microsoft YaHei", 12))
            b.setStyleSheet(
                "QPushButton { background: rgba(255,255,255,0.85); border: 1px solid #aaa;"
                " border-radius: 8px; } QPushButton:hover { background: #fff; }")
            b.clicked.connect(slot)
            row.addWidget(b)
        outer.addLayout(row)

        self._status = QLabel("")
        self._status.setAlignment(Qt.AlignCenter)
        self._status.setFont(QFont("Microsoft YaHei", 11))
        self._status.setStyleSheet("background: transparent; color: #2c7a2c;")
        outer.addWidget(self._status)
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
