"""启动画面"""

from PySide6.QtWidgets import QSplashScreen
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QBrush, QFont


def create_splash():
    pix = QPixmap(600, 400)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    gradient = QLinearGradient(0, 0, 0, 400)
    gradient.setColorAt(0, QColor(255, 255, 255))
    gradient.setColorAt(0.5, QColor(200, 225, 245))
    gradient.setColorAt(1, QColor(91, 167, 209))
    painter.fillRect(0, 0, 600, 400, QBrush(gradient))
    painter.setFont(QFont("STKaiti", 56, QFont.Bold))
    painter.setPen(QColor(26, 58, 92))
    painter.drawText(0, 0, 600, 280, Qt.AlignCenter, "庐州非遗")
    painter.setFont(QFont("Microsoft YaHei", 16))
    painter.setPen(QColor(26, 58, 92, 150))
    painter.drawText(0, 220, 600, 60, Qt.AlignCenter, "动态手势展示系统")
    painter.end()
    splash = QSplashScreen(pix)
    splash.show()
    return splash
