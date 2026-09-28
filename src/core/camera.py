"""摄像头采集线程

Windows 上实测踩过的坑，改这里之前务必先读：

1. **后端选不对会慢几十倍。** OpenCV 在 Windows 默认走 MSMF，部分 USB 摄像头
   在它下面光是"打开 + 设分辨率"就要几十秒：

       罗技外接   MSMF 38.8s   DSHOW 3.2s
       笔记本自带  MSMF  0.6s   DSHOW 1.5s

   MSMF 最坏 38.8s、DSHOW 最坏 3.2s，所以统一优先 DSHOW；自带摄像头多花不到
   1 秒，换来外接可用。原来的写法是"先探测一遍再打开一遍"，等于把最慢的操作
   做两次 —— 现在改成打开时顺手读一帧做验证，探测那步直接省掉。

2. **打开设备是阻塞操作，会吞掉关闭请求。** 如果 run() 在阻塞之后才置
   _running = True，那么阻塞期间调用的 stop() 会被这次赋值覆盖掉：线程继续跑、
   wait() 永远等不到 —— 表现出来就是"窗口关不掉"，同时日志还在刷重连。
   所以 _running 必须在任何阻塞操作**之前**置位，并且 stop() 的等待要有上限。

3. **热插拔要双向都能感知。** 打开设备只在启动时做一次，之后只有"读帧失败"
   才会重新枚举 —— 于是拔掉能退化、插上却感知不到。现在多了一个后台"侦察线程"
   专门找优先级更高的摄像头（见 _CameraScout），两件事分开做，互不干扰。
"""
import contextlib
import os
import threading
import time

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal, QMutex

from src import config


def _silence_opencv():
    """尽量关掉 OpenCV 自己的日志（打开不存在的索引会刷 ERROR）。

    OpenCV 5 换了 API，旧写法 cv2.setLogLevel(0) 已经不存在 ——
    原来那处调用被 try/except 兜住了，于是一直静默失效、探测时照刷屏。
    """
    for fn in (
        lambda: cv2.utils.logging.setLogLevel(cv2.utils.logging.LOG_LEVEL_SILENT),
        lambda: cv2.setLogLevel(0),
    ):
        try:
            fn()
            return
        except Exception:
            continue


# 导入即静音。注意别只是"定义了这个函数"就完事 —— 上一版就是这样，
# 函数写好了却没人调用，打开不存在的索引时照样刷一屏 ERROR/WARN。
_silence_opencv()


@contextlib.contextmanager
def _muted_stderr():
    """临时把 fd 2 指向 nul。OpenCV 后端有时绕过自己的日志直接往 stderr 写。"""
    saved = None
    try:
        saved = os.dup(2)
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, 2)
    except Exception:
        saved = None
    try:
        yield
    finally:
        if saved is not None:
            try:
                os.dup2(saved, 2)
                os.close(saved)
            except Exception:
                pass


def _backends():
    """按优先级返回候选后端。

    DSHOW 在 Windows 上对 USB 摄像头明显更快更稳（见模块开头的实测数据）；
    非 Windows 上没有 CAP_DSHOW，就只剩默认后端。
    CAMERA_PREFER_DSHOW=False 可以强制回默认后端。
    """
    cands = []
    if config.CAMERA_PREFER_DSHOW and hasattr(cv2, "CAP_DSHOW"):
        cands.append(("DSHOW", cv2.CAP_DSHOW))
    cands.append(("默认", cv2.CAP_ANY))
    return cands


# "未找到摄像头"的日志节流。必须是模块级的：离线后上层会不断重建线程，
# 节流状态放在实例里每次重建都会清零，结果就是每 3 秒刷一条（实测踩过）。
_NOT_FOUND_LOG_INTERVAL_MS = 20000
_last_not_found_log = [0.0]


def _log_not_found(tried):
    now = time.time() * 1000.0
    if now - _last_not_found_log[0] < _NOT_FOUND_LOG_INTERVAL_MS:
        return
    _last_not_found_log[0] = now
    print("[Camera] 未找到可用摄像头（已尝试索引 %s），稍后自动重试" % tried, flush=True)


def camera_candidates(max_idx: int = None) -> list:
    """按优先级给出要依次尝试的摄像头索引。

    自动选择时优先外接（非 0 号），再退回自带（0 号）。这里**不做预探测**：
    打开设备时本来就会读一帧验证，先探一遍等于把最慢的操作做两遍
    （实测外接在 MSMF 下探测 + 打开要 57 秒才能出画面）。

    ⚠ OpenCV 给的是索引不是设备名，无法指定"几号是哪个摄像头"，
    只能做"优先非 0 号"这个区分。
    """
    if not config.CAMERA_AUTO_SELECT:
        return [config.CAMERA_INDEX]
    n = config.CAMERA_SCAN_MAX if max_idx is None else max_idx
    return [i for i in range(n) if i != 0] + [0]


def try_open(idx: int):
    """打开指定索引并验证真的能出帧，返回 (cap, 后端名) / (None, 原因)。

    **必须读一帧才算数**：`isOpened()` 为真却一帧也读不出来的设备是存在的，
    光看构造成功会把坏设备当成好设备选进来，然后卡在"未开启"。
    """
    reason = "打不开"
    for name, flag in _backends():
        cap = None
        try:
            cap = cv2.VideoCapture(idx) if flag == cv2.CAP_ANY \
                else cv2.VideoCapture(idx, flag)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            ok, _ = cap.read()
        except Exception as e:
            ok = False
            reason = str(e)
        if ok:
            return cap, name
        reason = "打不开" if cap is None or not cap.isOpened() else "读不出帧"
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass
    return None, reason


class _CameraScout(threading.Thread):
    """后台侦察：当前用的是自带摄像头时，找找有没有外接可用，探到就交给采集线程。

    **为什么必须独立线程**：用 DSHOW 打开一个外接摄像头要 3 秒左右，放在采集
    线程里会让预览每隔几秒就卡住 3 秒。这里只负责"打开并放好"，画面切换由
    采集线程在下一轮循环里接手（park/pickup 模式），两边互不阻塞。

    外部（外接）已经是当前选择时不侦察 —— 它已经是最优，没有更好的了。
    """

    def __init__(self, owner: "CameraThread", interval_ms: int):
        super().__init__(name="camera-scout", daemon=True)
        self._owner = owner
        self._interval = max(0.5, interval_ms / 1000.0)
        self._stop_evt = threading.Event()

    def stop(self):
        self._stop_evt.set()

    def run(self):
        while not self._stop_evt.is_set():
            if not self._owner.wants_upgrade():
                self._stop_evt.wait(self._interval)
                continue
            found = None
            with _muted_stderr():
                for idx in camera_candidates():
                    if idx == 0 or self._stop_evt.is_set():
                        continue          # 0 号是当前用的，不必探
                    cap, info = try_open(idx)
                    if cap is not None:
                        found = (cap, idx, info)
                        break
            if found is None:
                self._stop_evt.wait(self._interval)
                continue
            self._owner.park(*found)
            self._stop_evt.wait(self._interval)


class CameraThread(QThread):
    frame_ready = Signal()

    # 读帧失败后先原地重试若干次（毫秒间隔），扛过瞬时抖动；
    # 连续失败到这个次数就认定"摄像头离线"，结束线程交给上层重新搜索重建。
    #
    # 为什么不在原地重开设备：手动"关闭摄像头 → 插拔 → 打开摄像头"这条路
    # 实测最可靠，因为它建的是**全新的线程 + 全新的 VideoCapture**。原地换句柄
    # （复用一个线程、一个 OpenCV 对象）在设备消失后可能残留状态、不如重建干净。
    # 所以自动恢复也走同一条路：退出 → 上层重建 → 重新枚举候选。
    READ_FAIL_SLEEP_MS = 100
    READ_FAIL_OFFLINE = 20          # 约 2 秒
    # stop() 最多等这么久（毫秒）。打开设备/读帧都可能阻塞很久，无限等会让窗口关不掉
    STOP_WAIT_MS = 3000

    def __init__(self, frame_buffer):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.cap = None
        self._idx = None
        self._current_frame = None
        self._mutex = QMutex()
        self._running = False
        self._signal_ok = True
        self._abandoned = False
        # 侦察线程交过来的"更好的摄像头"，由采集循环接手
        self._pending = None
        self._pending_lock = threading.Lock()
        self._scout = None

    # ---------------- 设备切换 ----------------
    def _release_cap(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _open_camera(self) -> bool:
        """按优先级依次尝试，第一个能出帧的就是它"""
        tried = []
        with _muted_stderr():
            for idx in camera_candidates():
                if not self._running:
                    return False
                tried.append(idx)
                cap, info = try_open(idx)
                if cap is not None:
                    self.cap, self._idx = cap, idx
                    print("[Camera] 已打开索引 %d（%s，%s）"
                          % (idx, "外接" if idx != 0 else "自带", info), flush=True)
                    return True
        _log_not_found(tried)
        return False

    # ---- 侦察线程 ↔ 采集线程的交接 ----
    def wants_upgrade(self) -> bool:
        """要不要去找更好的摄像头：当前用的是自带（0 号）时才值得找"""
        if not config.CAMERA_AUTO_SELECT:
            return False
        return self._idx == 0 and any(i != 0 for i in camera_candidates())

    def park(self, cap, idx: int, info: str):
        """侦察线程调用：把已打开的摄像头先存放好（放不下就把旧的释放掉）"""
        with self._pending_lock:
            old = self._pending
            self._pending = (cap, idx, info)
        if old is not None:
            try:
                old[0].release()
            except Exception:
                pass

    def _pickup(self):
        with self._pending_lock:
            item, self._pending = self._pending, None
        return item

    def _switch_to(self, cap, idx: int, info: str) -> bool:
        """切换到侦察线程探到的摄像头。成功返回 True。"""
        old = self._idx
        self._release_cap()
        self.cap, self._idx = cap, idx
        # 换了画面源，缓冲里是另一个摄像头的画面，继续用没有意义
        self.frame_buffer.clear()
        self._set_signal_ok(True)
        print("[Camera] 检测到外接摄像头，已从索引 %s 切换到 %d（%s）"
              % (old, idx, info), flush=True)
        return True

    # ---------------- 状态 ----------------
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

    def camera_index(self):
        """当前使用的索引；还没打开时为 None"""
        return self._idx

    # ---------------- 主循环 ----------------
    def run(self):
        # ⚠ _running 必须在任何阻塞操作之前置位。放在后面的话，如果打开设备期间
        # 有人调 stop()，这次赋值会把关闭请求覆盖掉 —— 线程继续跑、wait() 永远
        # 等不到，表现出来就是"窗口关不掉"。
        self._running = True
        try:
            if not self._open_camera():
                return
            self._scout = _CameraScout(self, config.CAMERA_UPGRADE_CHECK_MS)
            self._scout.start()
            self._loop()
        except Exception as e:                       # noqa: BLE001
            print("[Camera] 采集线程异常退出: %s" % e, flush=True)
        finally:
            # 线程结束了就别再让侦察线程空转（离线退出这条路上 stop() 不会被调用）
            if self._scout is not None:
                self._scout.stop()
            self._release_cap()
            with self._pending_lock:
                parked, self._pending = self._pending, None
            if parked is not None:
                try:
                    parked[0].release()
                except Exception:
                    pass

    def _loop(self):
        # CLAHE 只建一次：每帧新建一个对象纯属浪费
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)) \
            if config.CAMERA_ENHANCE_PREVIEW else None
        self._set_signal_ok(True)
        fails = 0        # 连续读帧失败次数

        while self._running:
            # 侦察线程探到更好的摄像头就换过去（换源会让画面短暂中断，属预期）
            pending = self._pickup()
            if pending is not None:
                self._switch_to(*pending)
                fails = 0

            ret, frame = self._read()
            if not ret:
                fails += 1
                self._set_signal_ok(False)
                if fails == 1:
                    print("[Camera] 读帧失败，可能掉线；自动重试中", flush=True)
                    # 掉线时清空缓冲：否则推理线程会一直对着最后那几十帧陈旧画面
                    # 反复推理（满速空转），悬浮窗也会停在旧结果上
                    self.frame_buffer.clear()
                if fails >= self.READ_FAIL_OFFLINE:
                    # 交给上层重建：外层（CameraWidget）会关掉本线程、重新搜索、
                    # 再开一个全新的 —— 与手动点按钮走的是同一条路
                    print("[Camera] 摄像头已离线，交给上层重新搜索", flush=True)
                    break
                self.msleep(self.READ_FAIL_SLEEP_MS)
                continue

            if fails:
                fails = 0
            self._set_signal_ok(True)

            # BGR -> RGB
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # 预览始终镜像（对用户自然）
            mirrored = cv2.flip(rgb, 1)

            # 喂给模型：干净 RGB（与 IPN-Hand 训练帧一致，不做 CLAHE/模糊）
            feed = mirrored if config.CAMERA_MIRROR_FEED else rgb
            self.frame_buffer.push(feed)

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
            # 这次 sleep 其实是"重复限速"：相机已经在按自己的节奏出帧，
            # 再睡一次会丢掉约 11% 的帧。实测（外接罗技 / 笔记本自带）：
            #     保持现状 26.8 / 27.4 fps      去掉这次 sleep 30.1 / 30.3 fps
            # 没去掉的原因：收益很小，而它决定的采样窗口长度（15 帧）
            # 从 0.56s 变成 0.50s —— 会改变喂给模型的时序输入，
            # 而现有参数都是在 0.56s 这一版上验证过的。要动就整批重新验证。
            self.msleep(1000 // config.CAMERA_FPS)

    def _read(self):
        try:
            return self.cap.read()
        except Exception as e:
            print("[Camera] 读帧异常: %s" % e, flush=True)
            return False, None

    # ---------------- 供 UI 读取 ----------------
    def get_frame(self) -> np.ndarray | None:
        self._mutex.lock()
        frame = self._current_frame.copy() if self._current_frame is not None else None
        self._mutex.unlock()
        return frame

    def request_stop(self):
        """只请求停止，**不等待**。

        给 UI 线程用：stop() 最多会阻塞 3 秒，放在 33ms 的界面定时器里会让界面卡住。
        线程可能正卡在驱动调用里，所以调用方需要另外轮询 isFinished()。
        """
        self._running = False

    def stop(self):
        """请求停止并等待退出。

        ⚠ 等待**必须有上限**：打开设备、读帧都可能阻塞很久（MSMF 下实测几十秒），
        无限等会让窗口关不掉。超时就放弃等待并标记为已弃用，让进程能正常退出
        —— 线程会在阻塞的那次调用返回后自行结束。
        """
        self._running = False
        if self._scout is not None:
            self._scout.stop()
            self._scout = None
        if not self.isRunning():
            return
        if not self.wait(self.STOP_WAIT_MS):
            self._abandoned = True
            print("[Camera] 采集线程未能在 %dms 内退出（多半卡在驱动调用里），"
                  "已放弃等待以便正常关闭" % self.STOP_WAIT_MS, flush=True)
