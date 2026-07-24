"""测试 F1: 摄像头预览"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget

from src.core.frame_buffer import FrameBuffer
from src.ui.camera_widget import CameraWidget


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Camera Test")
        self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 帧缓冲
        self.frame_buffer = FrameBuffer()

        # 摄像头
        self.camera = CameraWidget()
        layout.addWidget(self.camera)

        # 启动
        self.camera.start(self.frame_buffer)

    def closeEvent(self, event):
        self.camera.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec())
