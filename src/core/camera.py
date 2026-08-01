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
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 镜像翻转
            frame = cv2.flip(frame, 1)

            # 图像增强：CLAHE + 去噪
            lab = cv2.cvtColor(frame, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            frame = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
            frame = cv2.GaussianBlur(frame, (3, 3), 0)

            self._mutex.lock()
            self._current_frame = frame
            self._mutex.unlock()

            self.frame_buffer.push(frame)
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
