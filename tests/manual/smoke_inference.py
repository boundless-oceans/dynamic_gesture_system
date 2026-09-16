"""手工冒烟：摄像头 + 帧缓冲 + 推理线程

直接 `python tests/manual/smoke_inference.py` 运行（需要摄像头和显示器）。
10 秒后自动关闭，终端会逐条打印识别结果（含 top3 与即时/平滑两路置信度）。

用来观察模型对真实手势的反应，以及调整去抖/门槛参数前的基线表现。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (QApplication, QLabel, QMainWindow, QTextEdit, QVBoxLayout, QWidget)

from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer, InferenceThread
from src.ui.camera_widget import CameraWidget


class SmokeWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("冒烟：摄像头 + 推理")
        self.resize(800, 700)
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.status = QLabel("启动中…")
        layout.addWidget(self.status)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(240)
        layout.addWidget(self.log)

        self.frame_buffer = FrameBuffer()
        self.camera = CameraWidget()
        layout.addWidget(self.camera)

        self.recognizer = GestureRecognizer()
        if self.recognizer.status != "ok":
            print(f"[冒烟] 权重状态异常：{self.recognizer.status} {self.recognizer.status_detail}")
        self.inference_thread = InferenceThread(self.frame_buffer, self.recognizer)
        self.inference_thread.result_ready.connect(self._on_result)
        self.inference_thread.start()
        self.camera.start(self.frame_buffer)

        print("[冒烟] 已启动，10 秒后自动关闭")
        QTimer.singleShot(10000, self.close)

    def _on_result(self, result):
        from src.core.gesture_mapper import label_cn
        msg = ("平滑=%s(%.3f) 即时=%s(%.3f) top3=%s" % (
            label_cn(int(result["gesture"])), result["confidence"],
            label_cn(int(result.get("raw_gesture", result["gesture"]))),
            result.get("raw_confidence", 0.0), result["top3"]))
        self.status.setText(msg)
        self.log.append(msg)
        print(f"[冒烟] {msg}")

    def closeEvent(self, event):
        self.inference_thread.stop()
        self.camera.stop()
        print("[冒烟] 结束")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = SmokeWindow()
    win.show()
    sys.exit(app.exec())
