"""摄像头采集线程"""

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex

from src import config


class CameraThread(QThread):
    frame_ready = Signal()

    def __init__(self, frame_buffer):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.cap = None
        self._current_frame = None
        self._mutex = QMutex()
        self._running = False

    def run(self):
        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self._running = True

        while self._running:
            ret, frame = self.cap.read()
            if not ret:
                continue

            # BGR -> RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 预览始终镜像（对用户自然）
            mirrored = cv2.flip(rgb, 1)

            # 喂给模型：干净 RGB（与 IPN-Hand 训练帧一致，不做 CLAHE/模糊）
            feed = mirrored if config.CAMERA_MIRROR_FEED else rgb
            self.frame_buffer.push(feed)

            # 预览画面：可选 CLAHE + 去噪增强（仅显示用）
            preview = mirrored
            if config.CAMERA_ENHANCE_PREVIEW:
                lab = cv2.cvtColor(preview, cv2.COLOR_RGB2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                l = clahe.apply(l)
                lab = cv2.merge([l, a, b])
                preview = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
                preview = cv2.GaussianBlur(preview, (3, 3), 0)

            self._mutex.lock()
            self._current_frame = preview
            self._mutex.unlock()
            self.frame_ready.emit()
            self.msleep(1000 // config.CAMERA_FPS)

        self.cap.release()

    def get_frame(self) -> np.ndarray | None:
        self._mutex.lock()
        frame = self._current_frame.copy() if self._current_frame is not None else None
        self._mutex.unlock()
        return frame

    def stop(self):
        self._running = False
        self.wait()
