"""测试 F1: 摄像头 + 帧缓冲联调"""

import time
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtCore import QTimer

from src.core.frame_buffer import FrameBuffer
from src.ui.camera_widget import CameraWidget


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F1 Test: Camera + FrameBuffer")
        self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 状态标签
        self.status_label = QLabel("等待摄像头启动...")
        layout.addWidget(self.status_label)

        # 摄像头
        self.frame_buffer = FrameBuffer()
        self.camera = CameraWidget()
        layout.addWidget(self.camera)

        # 定时检查帧缓冲
        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self._check_buffer)
        self.check_timer.start(1000)

        # 5 秒后自动退出
        self.exit_timer = QTimer()
        self.exit_timer.timeout.connect(self.close)
        self.exit_timer.start(5000)

        # 启动
        self.camera.start(self.frame_buffer)
        self.status_label.setText("摄像头已启动，检测缓冲中...")
        print("[Test] 摄像头启动，5秒后自动关闭")

    def _check_buffer(self):
        size = self.frame_buffer.size
        self.status_label.setText(f"缓冲帧数: {size}")
        print(f"[Test] FrameBuffer size: {size}")

    def closeEvent(self, event):
        self.check_timer.stop()
        self.exit_timer.stop()
        self.camera.stop()
        print(f"[Test] 最终缓冲帧数: {self.frame_buffer.size}")
        print("[Test] F1 测试结束")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec())
