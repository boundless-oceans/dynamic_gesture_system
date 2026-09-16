"""摄像头预览组件"""

import json
import os

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QTimer, QRectF

from src.core.camera import CameraThread
from src.core.frame_buffer import FrameBuffer
from src.core.inference import model_view_rect
from src import config


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

    def set_confidence(self, gesture: str | None, confidence: float):
        label = "无手势" if gesture is None else _LABELS.get(gesture, f"ID:{gesture}")
        self._gesture_text.setText(f"{label}")
        self._conf_text.setText(f"{confidence*100:.1f}%")
        self._gesture_text.raise_()
        self._conf_text.raise_()

    def set_custom(self, text: str):
        """直接设置显示文本（用于"已执行"提示等），不带置信度"""
        self._gesture_text.setText(text)
        self._conf_text.setText("")
        self._gesture_text.raise_()
        self._conf_text.raise_()

    def _on_frame_ready(self):
        pass

    def _draw_zone(self, pixmap: QPixmap, frame_w: int, frame_h: int) -> QPixmap:
        """在预览上画出模型能看到的范围（手势交互区）

        模型只处理画面中央一块，四周看不到。把范围明示出来，访客就知道该站
        哪里、手该伸到哪儿；也能减少"画面里几个人各做各的"造成的互相干扰。
        框的位置由 model_view_rect 从预处理参数算出来，不写死。
        """
        if not config.CAMERA_SHOW_ZONE or frame_w <= 0 or frame_h <= 0:
            return pixmap
        zx, zy, zw, zh = model_view_rect(frame_w, frame_h)
        sx = pixmap.width() / float(frame_w)
        sy = pixmap.height() / float(frame_h)
        rect = QRectF(zx * sx, zy * sy, zw * sx, zh * sy)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(255, 179, 0, 210), 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)
        # 标语贴在框内顶部，避免压住画面主体
        painter.setPen(QPen(QColor(255, 179, 0, 235)))
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
        painter.drawText(rect.adjusted(4, 2, -4, 0),
                         Qt.AlignTop | Qt.AlignHCenter, "手势交互区 · 请将手伸入")
        painter.end()
        return pixmap

    def _update_frame(self):
        if self._camera_thread is None:
            return
        if not self._camera_thread.signal_ok():
            # 掉线时不要停在最后一帧（看起来像正常），明确提示正在重连
            self._label.setText("摄像头信号丢失\n正在自动重连…")
            self._label.setStyleSheet(
                "background-color: #1e1e1e; color: #e6a23c; font-size: 14px;")
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
        self._label.setPixmap(self._draw_zone(pixmap, w, h))
        self._gesture_text.raise_()
        self._conf_text.raise_()
