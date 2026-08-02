"""水墨粒子背景基类"""

import random
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QLinearGradient, QColor, QBrush


class BasePage(QWidget):
    """带水墨粒子背景的页面基类"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._particles = self._create_particles(200)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_particles)
        self._timer.start(50)

    def _create_particles(self, count: int):
        return [{
            'x': random.randint(0, 1280), 'y': random.randint(0, 800),
            'r': random.randint(2, 8), 'vx': random.uniform(-0.3, 0.3),
            'vy': random.uniform(-0.8, -0.2), 'opacity': random.uniform(0.08, 0.35),
            'color': random.choice([QColor(30, 60, 120), QColor(60, 100, 160), QColor(20, 40, 80)]),
        } for _ in range(count)]

    def _update_particles(self):
        for p in self._particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            if p['y'] < -20:
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

        for p in self._particles:
            c = QColor(p['color'])
            c.setAlphaF(p['opacity'])
            painter.setBrush(QBrush(c))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(int(p['x']), int(p['y']), p['r'], p['r'])

    def paintEvent(self, event):
        painter = QPainter(self)
        self._draw_background(painter)
