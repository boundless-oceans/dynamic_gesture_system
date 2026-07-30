"""摄像头预览组件"""

import json
import os

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap, QFont
from PySide6.QtCore import Qt, QTimer

from src.core.camera import CameraThread
from src.core.frame_buffer import FrameBuffer


def _load_labels():
    path = os.path.join(os.path.dirname(__file__), "../../assets/gestures.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_LABELS = _load_labels()


class CameraWidget(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_thread = None
        self._timer = QTimer(self)

        self._label = QLabel("摄像头未开启", self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setMinimumSize(320, 240)
        self._label.setStyleSheet("background-color: #1e1e1e; color: #888; font-size: 14px;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._gesture_text = QLabel("", self)
        self._gesture_text.setFixedWidth(240)
        self._gesture_text.move(2, 2)
        self._gesture_text.setFont(QFont("Consolas", 16, QFont.Bold))
        self._gesture_text.setStyleSheet("color: #f00; background: transparent;")

        self._conf_text = QLabel("", self)
        self._conf_text.setFixedWidth(240)
        self._conf_text.move(2, 24)
        self._conf_text.setFont(QFont("Consolas", 16))
        self._conf_text.setStyleSheet("color: #f00; background: transparent;")

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
        self._gesture_text.setText("")
        self._conf_text.setText("")
        self.update()

    def set_confidence(self, gesture: str, confidence: float):
        label = _LABELS.get(gesture, f"ID:{gesture}")
        self._gesture_text.setText(f"{label}")
        self._conf_text.setText(f"{confidence*100:.1f}%")
        self._gesture_text.raise_()
        self._conf_text.raise_()

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
        self._gesture_text.raise_()
        self._conf_text.raise_()
