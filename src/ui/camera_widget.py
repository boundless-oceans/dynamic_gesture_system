"""摄像头预览组件"""

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt, QTimer

from src.core.camera import CameraThread
from src.core.frame_buffer import FrameBuffer


class CameraWidget(QWidget):
    """摄像头实时预览"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_thread = None
        self._timer = QTimer(self)

        self._label = QLabel("摄像头未开启")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumSize(320, 240)
        self._label.setStyleSheet("background-color: #1e1e1e; color: #888; font-size: 14px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._timer.timeout.connect(self._update_frame)

    def start(self, frame_buffer: FrameBuffer):
        if self._camera_thread is not None:
            return
        self._camera_thread = CameraThread(frame_buffer)
        self._camera_thread.frame_ready.connect(self._on_frame_ready)
        self._camera_thread.start()
        self._timer.start(33)

    def stop(self):
        if self._camera_thread is None:
            return
        self._timer.stop()
        self._camera_thread.stop()
        self._camera_thread = None
        self._label.clear()
        self._label.setFixedSize(320, 240)
        self._label.setStyleSheet("background-color: #1e1e1e; color: #888; font-size: 14px;")
        self._label.setText("摄像头未开启")
        self.update()

    def _on_frame_ready(self):
        pass

    def _update_frame(self):
        if self._camera_thread is None:
            return
        frame = self._camera_thread.get_frame()
        if frame is None:
            return
        h, w, ch = frame.shape
        qt_image = QImage(frame.data, w, h, ch * w, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image).scaled(
            self._label.width(), self._label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._label.setPixmap(pixmap)
