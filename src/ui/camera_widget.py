"""摄像头预览组件"""

import json
import os
import time

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

    # 摄像头离线后，隔多久重建一次（毫秒）。重建 = 关掉旧线程 + 重新搜索 + 开新线程，
    # 与手动点「关闭摄像头 → 打开摄像头」完全同一条路 —— 那条路实测最可靠。
    RECOVER_INTERVAL_MS = 3000

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_thread = None
        # 用户是否**希望**摄像头开着（区别于"此刻线程在不在跑"）。
        # 手动关掉摄像头后不该被自动重建，靠的就是这个标志。
        self._wanted = False
        self._frame_buffer = None
        self._next_try_ms = 0.0
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
        # 采集线程已经结束（离线后自行退出 / 一个摄像头都没找到）：
        # 用户还希望开着的话，隔一会儿重建一次——与手动"关掉再打开"同一条路
        if not self._camera_thread.isRunning():
            if not self._wanted:
                return
            if time.time() * 1000.0 >= self._next_try_ms:
                self._recover()
            else:
                # 重建也没找到摄像头，正在等下一次重试——把状态说清楚，
                # 别一直停在"正在打开…"让人以为卡住了
                self._show_placeholder("未找到可用摄像头\n正在自动重试…")
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
