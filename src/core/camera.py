"""摄像头采集线程"""

import os

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex

from src import config


def _probe(idx: int) -> bool:
    """探测某个索引的摄像头是否可用（能打开并读到一帧）"""
    cap = None
    try:
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            return False
        ok, _ = cap.read()
        return bool(ok)
    except Exception:
        return False
    finally:
        if cap is not None:
            cap.release()


def pick_camera_index(max_idx: int = 5) -> int:
    """选择摄像头索引：优先外接（非 0 号），没有外接则用自带（0 号）。"""
    if not config.CAMERA_AUTO_SELECT:
        return config.CAMERA_INDEX
    # 枚举期间静音 OpenCV 日志 + 底层 stderr（无效索引会刷 ERROR）
    prev_level = None
    saved_fd = None
    try:
        prev_level = cv2.getLogLevel()
        cv2.setLogLevel(0)  # SILENT
    except Exception:
        prev_level = None
    try:
        saved_fd = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
    except Exception:
        saved_fd = None
    try:
        found = [i for i in range(max_idx) if _probe(i)]
    finally:
        if saved_fd is not None:
            try:
                os.dup2(saved_fd, 2); os.close(saved_fd)
            except Exception:
                pass
        if prev_level is not None:
            try: cv2.setLogLevel(prev_level)
            except Exception: pass

    if not found:
        print("[Camera] 未探测到可用摄像头，回退 CAMERA_INDEX =", config.CAMERA_INDEX)
        return config.CAMERA_INDEX
    external = [i for i in found if i != 0]
    chosen = external[0] if external else found[0]
    print(f"[Camera] 可用索引 {found} → 选用 {chosen} "
          f"({'外接' if chosen != 0 else '自带'})")
    return chosen


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
        idx = pick_camera_index()
        self.cap = cv2.VideoCapture(idx)
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
