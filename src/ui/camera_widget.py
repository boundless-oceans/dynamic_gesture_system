"""摄像头预览组件"""

import json
import math
import time
from collections import deque

from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PySide6.QtGui import QImage, QPixmap, QFont, QPainter, QPen, QColor
from PySide6.QtCore import Qt, QTimer, QRectF

from src.core.camera import CameraThread
from src.core.frame_buffer import FrameBuffer
from src.core.inference import model_view_rect
from src import config
from src import paths


def _load_labels():
    path = paths.resource_path("assets", "gestures.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_LABELS = _load_labels()

# 手势交互区框的透明度范围。关掉呼吸时用 STATIC，与加呼吸之前的样子一致
# （所以"关掉开关"是真正的无变化，而不是换了个亮度）。
ZONE_ALPHA_MIN = 130
ZONE_ALPHA_MAX = 235
ZONE_ALPHA_STATIC = 210


def zone_breath_alpha(t_ms: float) -> int:
    """交互区框此刻该用多大的透明度（0~255）。

    刻意做成**纯函数**：呼吸效果本身没法单测，但"透明度随时间在上下限之间往返"
    可以 —— 直接喂时间戳断言即可，不用起摄像头也不用等。

    用 cos 波（0 → 1 → 0），首尾都落在最小值上，所以周期与周期之间不会"跳"一下。
    """
    if not config.CAMERA_ZONE_BREATH:
        return ZONE_ALPHA_STATIC
    period = config.CAMERA_ZONE_BREATH_MS
    if period <= 0:
        return ZONE_ALPHA_STATIC
    phase = (t_ms % period) / float(period)
    wave = 0.5 - 0.5 * math.cos(2.0 * math.pi * phase)
    return int(round(ZONE_ALPHA_MIN + wave * (ZONE_ALPHA_MAX - ZONE_ALPHA_MIN)))


class CameraWidget(QWidget):

    # 摄像头离线后，隔多久重建一次（毫秒）。重建 = 关掉旧线程 + 重新搜索 + 开新线程，
    # 与手动点「关闭摄像头 → 打开摄像头」完全同一条路 —— 那条路实测最可靠。
    RECOVER_INTERVAL_MS = 3000
    # 帧率健康判据：最近 HEALTH_WINDOW_MS 内至少要有 MIN_FRAMES_IN_WINDOW 帧。
    # 正常采集约 27fps（3 秒约 80 帧），所以这个下限宽松到不会误伤，
    # 但足以抓住"半死"状态（大部分失败、偶尔挤出一帧）。
    HEALTH_WINDOW_MS = 3000
    MIN_FRAMES_IN_WINDOW = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_thread = None
        # 用户是否**希望**摄像头开着（区别于"此刻线程在不在跑"）。
        # 手动关掉摄像头后不该被自动重建，靠的就是这个标志。
        self._wanted = False
        self._frame_buffer = None
        self._next_try_ms = 0.0
        self._last_frame_ms = 0.0     # 最近一次收到画面的时刻
        self._first_frame_ms = 0.0    # 本线程第一帧的时刻（健康判据的起算点）
        self._frame_times = deque(maxlen=200)   # 最近收到的帧的时刻，用来算帧率
        self._recovering = False      # 已请求停止、正在等旧线程真正结束
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

        # 静态手势（HaGRID 34 类）的读数。**诊断用**，见 config.CAMERA_SHOW_STATIC ——
        # 上面两行是动态模型（认"手的动作"），这一行是静态模型（认"手此刻的形状"），
        # 两个模型、两回事，摆在一起是为了现场核对"不裁手到底行不行"。
        self._static_text = QLabel("", self)
        self._static_text.setFixedWidth(240)
        self._static_text.move(2, 48)
        self._static_text.setFont(QFont("Consolas", 12))
        self._static_text.setStyleSheet("color: #00e5ff; background: transparent;")

        self._timer.timeout.connect(self._update_frame)

    def start(self, frame_buffer: FrameBuffer):
        if self._camera_thread is not None:
            return
        self._wanted = True
        self._frame_buffer = frame_buffer
        self._spawn()

    def _spawn(self, placeholder="正在打开摄像头…"):
        """建一个全新的采集线程（重建与首次打开走的是同一条路）"""
        if self._camera_thread is not None:
            return
        # 打开摄像头可能要几秒（外接 USB 尤其慢），先给个提示而不是
        # 一直停在"摄像头未开启"——后者看起来像坏了，让人以为设备没接上
        self._show_placeholder(placeholder)
        # 时间戳清零 = 看门狗先解除武装：新线程刚起来还没出帧时，
        # 不能拿上一个线程留下的旧时间戳去判它"失联"
        self._last_frame_ms = 0.0
        self._first_frame_ms = 0.0
        self._frame_times.clear()
        self._recovering = False
        self._camera_thread = CameraThread(self._frame_buffer)
        self._camera_thread.frame_ready.connect(self._on_frame_ready)
        self._camera_thread.start()
        # 刚 start() 时 QThread.isRunning() 可能还短暂为 False，
        # 这里先压一个"最早重试时刻"，避免被误判成"线程已结束"而立刻重建
        self._next_try_ms = time.time() * 1000.0 + self.RECOVER_INTERVAL_MS
        self._timer.start(33)

    def _recover(self):
        """摄像头离线后自动重建：关掉旧线程 → 重新搜索 → 开新线程。

        采集线程在读帧连续失败后会把 _running 置回 false 并自行结束，
        这里负责收尾并把整条链路重建一遍。
        """
        self._next_try_ms = time.time() * 1000.0 + self.RECOVER_INTERVAL_MS
        old = self._camera_thread
        # 说清楚"为什么重建"：采集线程结束的原因分散在几处（离线、一个摄像头都找不到），
        # 只看到后面那行"已打开索引 x"会让人不知道中间发生了什么
        print("[Camera] 采集线程已结束（此前索引 %s），重新搜索…"
              % (old.camera_index() if old is not None else None), flush=True)
        self._camera_thread = None
        if old is not None:
            try:
                old.stop()          # 线程多半已结束，stop() 会立刻返回
            except Exception:
                pass
            old.deleteLater()
        self._spawn("摄像头已断开\n正在重新搜索…")

    def _show_placeholder(self, text: str):
        self._label.setPixmap(QPixmap())
        self._label.setStyleSheet(
            "background-color: #1e1e1e; color: #e6a23c; font-size: 14px;")
        self._label.setText(text)

    def stop(self):
        self._wanted = False            # 手动关掉后不再自动重建
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
        self._static_text.setText("")
        self.update()

    def set_confidence(self, gesture: str | None, confidence: float):
        label = "无手势" if gesture is None else _LABELS.get(gesture, f"ID:{gesture}")
        self._gesture_text.setText(f"{label}")
        self._conf_text.setText(f"{confidence*100:.1f}%")
        self._gesture_text.raise_()
        self._conf_text.raise_()

    def set_static(self, label: str | None, confidence: float):
        """显示静态手势模型（HaGRID 34 类）的读数。**诊断用**。

        关掉 `config.CAMERA_SHOW_STATIC` 就连控件一起藏起来，不留一行空白。
        """
        if not config.CAMERA_SHOW_STATIC or label is None:
            self._static_text.setVisible(False)
            return
        self._static_text.setVisible(True)
        self._static_text.setText(f"静态: {label} {confidence*100:.0f}%")
        self._static_text.raise_()

    def _on_frame_ready(self):
        """每出一帧就记时间戳：看门狗靠它算「最近这段时间出了几帧」"""
        now = time.time() * 1000.0
        self._last_frame_ms = now
        if not self._first_frame_ms:
            self._first_frame_ms = now
        self._frame_times.append(now)
        self._recovering = False

    def _frames_in_window(self) -> int:
        """最近一个统计窗口内收到的帧数"""
        now = time.time() * 1000.0
        while self._frame_times and now - self._frame_times[0] > self.HEALTH_WINDOW_MS:
            self._frame_times.popleft()
        return len(self._frame_times)

    def _camera_unhealthy(self, now: float) -> bool:
        """画面是不是已经不可用了

        必须等"出过第一帧、且满了一个统计窗口"之后才判 ——
        否则刚启动/刚重建时窗口里没帧，会被当成失联而立刻重启，陷入循环。
        """
        if not self._first_frame_ms:
            return False
        if now - self._first_frame_ms <= self.HEALTH_WINDOW_MS:
            return False
        return self._frames_in_window() < self.MIN_FRAMES_IN_WINDOW

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
        # 呼吸：让框缓慢明暗。它不动的话在画面里就是一条静止虚线，很容易被忽略 ——
        # 这里每帧都会被重绘（_update_frame 约 33ms 一次），所以按时间算透明度即可，
        # 不需要额外的定时器。
        alpha = zone_breath_alpha(time.time() * 1000.0)
        painter.setPen(QPen(QColor(255, 179, 0, alpha), 2, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)
        # 标语贴在框内顶部，避免压住画面主体（比框稍亮一点，保持主次）
        painter.setPen(QPen(QColor(255, 179, 0, min(255, alpha + 25))))
        painter.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
        painter.drawText(rect.adjusted(4, 2, -4, 0),
                         Qt.AlignTop | Qt.AlignHCenter, "手势交互区 · 请将手伸入")
        painter.end()
        return pixmap

    def _update_frame(self):
        if self._camera_thread is None:
            return
        # 采集线程已经结束（离线后自行退出 / 一个摄像头都没找到）：
        # 用户还希望开着的话，隔一会儿重建一次——与手动"关掉再打开"同一条路
        now = time.time() * 1000.0
        if not self._camera_thread.isRunning():
            if not self._wanted:
                return
            if now >= self._next_try_ms:
                self._recover()
            else:
                # 重建也没找到摄像头，正在等下一次重试——把状态说清楚，
                # 别一直停在"正在打开…"让人以为卡住了
                self._show_placeholder("未找到可用摄像头\n正在自动重试…")
            return

        # ---- 看门狗：线程还活着，但画面已经不可用了 ----
        #
        # 判据是**帧率塌了**，不是"完全没帧"。
        # 实测拔掉 USB 后摄像头常进入"半死"状态：大部分读帧失败，但偶尔挤出一帧。
        # 那样的干扰下，"连续失败 20 次"永远攒不满、"5 秒没有新帧"也永远够不到
        # ——两个判据都被绕过，画面却已经完全不可用了（卡顿、跳变、偏色）。
        # 换成"最近 3 秒收到了几帧"，半死和全死都能抓到。
        if self._camera_unhealthy(now):
            if not self._recovering:
                self._recovering = True
                print("[Camera] 画面异常（最近 %d 秒只有 %d 帧），判定失联，重启采集线程"
                      % (self.HEALTH_WINDOW_MS // 1000, self._frames_in_window()), flush=True)
                # 只请求、不等待：线程多半正卡在驱动里，等它会卡住界面
                self._camera_thread.request_stop()
                # 已经决定重启了，就别再让 RECOVER_INTERVAL_MS 的冷却再拖几秒：
                # 旧线程一结束就立刻重建
                self._next_try_ms = 0.0
            elif self._camera_thread.isFinished():
                # ⚠ 必须确认旧线程**真的结束了**才能建新的。
                # 否则两个线程同时开着同一个摄像头：画面会在两者之间来回跳
                # （实测：预览不停在"对称"的两个视角间切换、颜色忽冷忽暖）。
                self._recover()
            else:
                self._show_placeholder("摄像头已断开\n正在重启…")
            return

        if not self._camera_thread.signal_ok():
            # 掉线时不要停在最后一帧（看起来像正常），明确提示正在重连
            self._show_placeholder("摄像头信号丢失\n正在自动重连…")
            return
        frame = self._camera_thread.get_frame()
        if frame is None:
            # 还没出过帧（正在打开设备 / 未找到摄像头）——保持"正在打开…"提示，
            # 不要显示成"未开启"让人以为设备没插
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
        if self._static_text.isVisible():
            self._static_text.raise_()
