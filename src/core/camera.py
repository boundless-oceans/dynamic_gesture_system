"""摄像头采集线程"""

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex

from src import config


class CameraThread(QThread):
    """摄像头采集线程：持续读取帧，存入共享缓冲"""

    frame_ready = Signal()   # 通知 UI 有新帧可读

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

            # 存入共享区（供 UI 读取）
            self._mutex.lock()
            self._current_frame = frame
            self._mutex.unlock()

            # 推入帧缓冲（供推理线程）
            self.frame_buffer.push(frame)

            # 通知 UI
            self.frame_ready.emit()

            # 控制帧率
            self.msleep(1000 // config.CAMERA_FPS)

        self.cap.release()

    def get_frame(self) -> np.ndarray | None:
        """主线程安全读取当前帧"""
        self._mutex.lock()
        frame = self._current_frame.copy() if self._current_frame is not None else None
        self._mutex.unlock()
        return frame

    def stop(self):
        self._running = False
        self.wait()
