"""置信度悬浮面板"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ConfidenceOverlay(QWidget):
    """摄像头旁显示当前手势 + 置信度"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(180, 100)
        self.setStyleSheet("""
            QWidget {
                background: rgba(30,30,30,0.85);
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self.label_gesture = QLabel("手势: --")
        self.label_gesture.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        self.label_gesture.setStyleSheet("color: #0f0; background: transparent;")
        self.label_gesture.setAlignment(Qt.AlignCenter)

        self.label_conf = QLabel("置信度: --%")
        self.label_conf.setFont(QFont("Microsoft YaHei", 11))
        self.label_conf.setStyleSheet("color: #0f0; background: transparent;")
        self.label_conf.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.label_gesture)
        layout.addWidget(self.label_conf)

    def update_result(self, gesture: str, confidence: float):
        self.label_gesture.setText(f"手势: {gesture}")
        self.label_conf.setText(f"置信度: {confidence*100:.1f}%")
