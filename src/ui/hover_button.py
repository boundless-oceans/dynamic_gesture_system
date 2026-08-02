"""悬浮按钮"""
from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PySide6.QtGui import QColor


class HoverButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._s = QGraphicsDropShadowEffect()
        self._s.setBlurRadius(6); self._s.setOffset(0,2)
        self._s.setColor(QColor(0,0,0,50))
        self.setGraphicsEffect(self._s)
    def enterEvent(self,e):
        self._s.setBlurRadius(20); self._s.setOffset(0,8)
        self._s.setColor(QColor(0,0,0,100))
        self.move(self.x(),self.y()-4)
        super().enterEvent(e)
    def leaveEvent(self,e):
        self._s.setBlurRadius(6); self._s.setOffset(0,2)
        self._s.setColor(QColor(0,0,0,50))
        self.move(self.x(),self.y()+4)
        super().leaveEvent(e)
