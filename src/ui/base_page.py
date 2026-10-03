"""水墨粒子背景基类

首页 / 详情页 / 传承人页都继承它（设置页是自己画的，不用这个）。

⚠ **粒子定时器只在页面可见时跑**（见 `showEvent` / `hideEvent`）。
它每 50ms 就把**整个页面**重绘一次；原先是在构造函数里无条件 `start()` 的，
于是页面藏起来之后还在按 20fps 空转 —— 展台 24 小时开着，这是白烧的 CPU。

⚠ 子类**重写 `showEvent` / `hideEvent` 时必须调 `super()`**，
否则粒子的启停会断掉（`tests/test_ui_feedback.py` 里有一条专门守这个）。
"""

import random

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QWidget

from src import config

# 三种墨色。透明度随粒子不同，所以颜色对象在创建粒子时**逐个烘好**。
_INK_RGB = [(30, 60, 120), (60, 100, 160), (20, 40, 80)]


class BasePage(QWidget):
    """带水墨粒子背景的页面基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._particles = self._create_particles(config.INK_PARTICLE_COUNT)
        self._timer = QTimer(self)
        self._timer.setInterval(config.INK_PARTICLE_MS)
        self._timer.timeout.connect(self._update_particles)
        # 刻意**不在这里 start()** —— 交给 showEvent，别让藏起来的页面空转

    def _create_particles(self, count: int):
        """随机撒一批"墨点"。

        ⚠ 颜色在这里就**连透明度一起烘好**（透明度是固定的，一辈子不变）。
        原先每帧都要 `QColor(p['color'])` + `setAlphaF()` 现造一个 ——
        粒子 300 个、20fps，就是每秒 6000 个白造的对象。
        """
        out = []
        for _ in range(count):
            c = QColor(*random.choice(_INK_RGB))
            c.setAlphaF(random.uniform(0.08, 0.35))
            out.append({
                'x': random.randint(0, 1280), 'y': random.randint(0, 800),
                'r': random.randint(2, 8), 'vx': random.uniform(-0.3, 0.3),
                'vy': random.uniform(-0.8, -0.2),
                'brush': QBrush(c),      # 画笔也一起备好（QBrush 是隐式共享的，拷一份很便宜）
            })
        return out

    def _update_particles(self):
        for p in self._particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            if p['y'] < -20:             # 飘出上边就从下边重新进来
                p['y'] = self.height() + 20
                p['x'] = random.randint(0, max(self.width(), 1))
        self.update()

    def _draw_background(self, painter: QPainter):
        """绘制渐变背景 + 粒子"""
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, QColor(255, 255, 255))
        gradient.setColorAt(1.0, QColor(91, 167, 209))
        painter.fillRect(self.rect(), gradient)

        painter.setPen(Qt.NoPen)         # 原先在循环里逐粒设置，其实是同一个值
        for p in self._particles:
            painter.setBrush(p['brush'])
            painter.drawEllipse(int(p['x']), int(p['y']), p['r'], p['r'])

    def paintEvent(self, event):
        painter = QPainter(self)
        self._draw_background(painter)

    # ---- 粒子只在页面可见时跑 ----
    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()
