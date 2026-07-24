"""线程安全的环形帧缓冲队列"""

import threading
from collections import deque

import numpy as np


class FrameBuffer:
    """环形帧缓冲，线程安全"""

    def __init__(self, maxlen: int = 32):
        self._buffer = deque(maxlen=maxlen)
        self._lock = threading.Lock()

    def push(self, frame: np.ndarray):
        """推入一帧（摄像头线程调用）"""
        with self._lock:
            self._buffer.append(frame.copy())

    def get_latest(self, n: int) -> list:
        """取出最近 n 帧（推理线程调用），不足 n 帧则返回空列表"""
        with self._lock:
            if len(self._buffer) < n:
                return []
            return list(self._buffer)[-n:]

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def clear(self):
        with self._lock:
            self._buffer.clear()
