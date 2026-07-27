"""测试 F2: 推理线程联调（F1 + F2a + F2 一起跑）"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QTextEdit
from PySide6.QtCore import QTimer

from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer, InferenceThread
from src.ui.camera_widget import CameraWidget


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("F2 Test: Camera + Buffer + Inference")
        self.resize(800, 600)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 状态
        self.status_label = QLabel("启动中...")
        layout.addWidget(self.status_label)

        # 推理结果日志
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        layout.addWidget(self.log)

        # 摄像头
        self.frame_buffer = FrameBuffer()
        self.camera = CameraWidget()
        layout.addWidget(self.camera)

        # 推理
        self.recognizer = GestureRecognizer()
        self.inference_thread = InferenceThread(self.frame_buffer, self.recognizer)
        self.inference_thread.result_ready.connect(self._on_result)
        self.inference_thread.start()

        # 启动摄像头
        self.camera.start(self.frame_buffer)

        # 10 秒后自动退出
        QTimer.singleShot(10000, self.close)

    def _on_result(self, result):
        gesture = result["gesture"]
        conf = result["confidence"]
        top3 = result["top3"]
        msg = f"gesture={gesture}, conf={conf:.4f}, top3={top3}"
        self.status_label.setText(msg)
        self.log.append(msg)
        print(f"[F2 Test] {msg}")

    def closeEvent(self, event):
        self.inference_thread.stop()
        self.camera.stop()
        print("[F2 Test] 测试结束")
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TestWindow()
    win.show()
    sys.exit(app.exec())
