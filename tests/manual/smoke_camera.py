"""手工冒烟：摄像头 + 帧缓冲 + 预览悬浮窗

直接 `python tests/manual/smoke_camera.py` 运行（需要摄像头和显示器）。
5 秒后自动关闭，终端会打印帧缓冲的增长情况。

自动化测试里不跑这个：它要真实摄像头，而且只能靠肉眼看画面。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget)

from src.core.frame_buffer import FrameBuffer
from src.ui.camera_widget import CameraWidget


class SmokeWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("冒烟：摄像头 + 帧缓冲")
        self.resize(800, 600)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.status = QLabel("等待摄像头启动…")
        layout.addWidget(self.status)

        self.frame_buffer = FrameBuffer()
        self.camera = CameraWidget()
        layout.addWidget(self.camera)

        self.timer = QTimer()
        self.timer.timeout.connect(self._check)
        self.timer.start(1000)

        self.camera.start(self.frame_buffer)
        print("[冒烟] 摄像头已启动，5 秒后自动关闭")
        QTimer.singleShot(5000, self.close)

    def _check(self):
        size = self.frame_buffer.size
        self.status.setText(f"缓冲帧数: {size}")
        print(f"[冒烟] FrameBuffer size = {size}, 画面正常 = {self.camera._camera_thread.signal_ok()}")

    def closeEvent(self, event):
        self.timer.stop()
        self.camera.stop()
        print(f"[冒烟] 结束，最终缓冲帧数 = {self.frame_buffer.size}")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SmokeWindow()
    win.show()
    sys.exit(app.exec())
