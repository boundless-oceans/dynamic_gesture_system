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
        print("[Camera] 未探测到可用摄像头，回退 CAMERA_INDEX =", config.CAMERA_INDEX, flush=True)
        return config.CAMERA_INDEX
    external = [i for i in found if i != 0]
    chosen = external[0] if external else found[0]
    # flush=True：输出重定向到文件时（现场排查）不带 flush 的日志会丢
    print(f"[Camera] 可用索引 {found} → 选用 {chosen} "
          f"({'外接' if chosen != 0 else '自带'})", flush=True)
    return chosen


class CameraThread(QThread):
    frame_ready = Signal()

    # 读帧失败处理：短暂休眠避免满核空转；连续失败到阈值则尝试重新打开设备
    READ_FAIL_SLEEP_MS = 100
    READ_FAIL_REOPEN = 30

    def __init__(self, frame_buffer, motion_gate=None):
        super().__init__()
        self.frame_buffer = frame_buffer
        # 动静门控：本线程每帧顺手喂一张缩略图判"有没有动"，
        # 推理线程据此跳过静止时段（这里大部分时间阻塞在 cap.read()，算这个几乎免费）
        self.motion_gate = motion_gate
        self.cap = None
        self._idx = config.CAMERA_INDEX
        self._current_frame = None
        self._mutex = QMutex()
        self._running = False
        self._signal_ok = True

    def _open(self):
        """打开摄像头并设置采集分辨率"""
        cap = cv2.VideoCapture(self._idx)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        return cap

    def _reopen(self):
        """掉线后尝试重新打开设备（USB 松脱/被抢占后插回可自动恢复）"""
        try:
            self.cap.release()
        except Exception:
            pass
        try:
            self.cap = self._open()
        except Exception as e:
            print(f"[Camera] 重新打开设备失败: {e}", flush=True)

    def _set_signal_ok(self, ok: bool):
        self._mutex.lock()
        self._signal_ok = ok
        self._mutex.unlock()

    def signal_ok(self) -> bool:
        """摄像头是否正常出帧（掉线时为 False，供预览层显示提示而非停在旧画面）"""
        self._mutex.lock()
        ok = self._signal_ok
        self._mutex.unlock()
        return ok

    def run(self):
        self._idx = pick_camera_index()
        self.cap = self._open()
        # CLAHE 只建一次：每帧新建一个对象纯属浪费
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) \
            if config.CAMERA_ENHANCE_PREVIEW else None
        self._running = True
        self._set_signal_ok(True)
        fails = 0

        while self._running:
            try:
                ret, frame = self.cap.read()
            except Exception as e:
                print(f"[Camera] 读帧异常: {e}", flush=True)
                ret, frame = False, None
            if not ret:
                # 掉线：休眠避免满核空转；连续失败到阈值重开设备，否则插回去也救不回来
                fails += 1
                if fails == 1:
                    print("[Camera] 读帧失败，可能掉线；将自动重试重连", flush=True)
                if fails % self.READ_FAIL_REOPEN == 0:
                    print(f"[Camera] 连续失败 {fails} 次，重新打开设备 {self._idx}", flush=True)
                    self._reopen()
                    fails = 0
                self._set_signal_ok(False)
                self.msleep(self.READ_FAIL_SLEEP_MS)
                continue

            if not self._signal_ok:
                print("[Camera] 画面已恢复", flush=True)
            self._set_signal_ok(True)
            fails = 0

            # BGR -> RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 预览始终镜像（对用户自然）
            mirrored = cv2.flip(rgb, 1)

            # 喂给模型：干净 RGB（与 IPN-Hand 训练帧一致，不做 CLAHE/模糊）
            feed = mirrored if config.CAMERA_MIRROR_FEED else rgb
            self.frame_buffer.push(feed)
            # 顺手判一次动静（用喂模型的同一张图，避免被预览增强干扰判断）
            if self.motion_gate is not None:
                self.motion_gate.feed(feed)

            # 预览画面：可选 CLAHE + 去噪增强（仅显示用）
            preview = mirrored
            if clahe is not None:
                lab = cv2.cvtColor(preview, cv2.COLOR_RGB2LAB)
                l, a, b = cv2.split(lab)
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
