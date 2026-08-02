"""主窗口：4页框架 + 摄像头悬浮窗 + 手势控制"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget, QLabel, QPushButton
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer, InferenceThread
from src.core.gesture_mapper import CONTROL_GESTURES, index_to_control
from src.ui.camera_widget import CameraWidget
from src.ui.home_page import HomePage
from src.ui.detail_page import DetailPage
from src.ui.viewer_page import ViewerPage
from src.ui.inheritor_page import InheritorPage
from src.ui.settings_page import SettingsPage
from src import config
from src.logger import get_logger

log = get_logger()


class _PlaceholderPage(QWidget):
    """占位页面（F8/F9/F10 实现前使用）"""

    def __init__(self, name: str, color: str):
        super().__init__()
        self.setStyleSheet(f"background-color: {color};")
        label = QLabel(name)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("font-size: 48px; color: white; background: transparent;")
        layout = QVBoxLayout(self)
        layout.addWidget(label)
        # 纵向导航按钮：从上到下排列
        nav = QVBoxLayout()
        nav.setAlignment(Qt.AlignCenter)
        self.btn_home = QPushButton("回到首页")
        self.btn_detail = QPushButton("详情页")
        self.btn_3d = QPushButton("3D查看")
        self.btn_home.setFixedWidth(150)
        self.btn_detail.setFixedWidth(150)
        self.btn_3d.setFixedWidth(150)
        nav.addWidget(self.btn_home)
        nav.addWidget(self.btn_detail)
        nav.addWidget(self.btn_3d)
        layout.addLayout(nav)


class MainWindow(QMainWindow):
    """非遗动态手势展示主窗口"""

    # 手势操作信号（F8/F9/F10 页面接收）
    signal_gesture_action = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("非遗动态手势展示系统")
        self.resize(1280, 800)

        # ---- 核心模块 ----
        self.frame_buffer = FrameBuffer()
        self.recognizer = GestureRecognizer()

        # ---- 4 页框架 ----
        self.stack = QStackedWidget()
        self.pages = {
            "inheritor": InheritorPage(),                     # 0
"home":     HomePage(),                              # index 0
"inheritor": InheritorPage(),                     # 0
            "detail":   DetailPage(),                          # index 1
            "viewer":   ViewerPage(),                           # index 2
            "settings": SettingsPage(),                        # index 3
        }
        self.page_index = {"inheritor": 0, "home": 1, "detail": 2, "viewer": 3, "settings": 4}
        for p in self.pages.values():
            self.stack.addWidget(p)
        self.stack.setCurrentIndex(1)  # 默认首页

        central = QWidget()
        central.setStyleSheet("background: transparent;")
        self.stack.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        self.pages["home"].go_inheritor.connect(lambda: self.stack.setCurrentIndex(0))
        layout.addWidget(self.stack)
        self.setCentralWidget(central)

        # HomePage: 点击项目 → 进入详情
        self.pages["home"].item_selected.connect(self._go_detail)
        # HomePage: 关闭/打开摄像头
        
        self.pages["settings"].go_home.connect(lambda: self.stack.setCurrentIndex(1))
        self.pages["inheritor"].go_home.connect(lambda: self.stack.setCurrentIndex(1))
        self.pages["detail"].go_home.connect(lambda: self.stack.setCurrentIndex(1))
        self.pages["detail"].go_viewer.connect(lambda: self.stack.setCurrentIndex(2))

        self.pages["detail"].go_viewer.connect(lambda: self.stack.setCurrentIndex(2))
        self.pages["viewer"].go_home.connect(lambda: self.stack.setCurrentIndex(2))
        # ---- 占位页按钮绑定（跳过 HomePage） ----
        for name, p in self.pages.items():
            if name in ("home", "detail", "viewer", "settings", "inheritor"):
                continue
            p.btn_home.clicked.connect(lambda: self.stack.setCurrentIndex(0))
            p.btn_detail.clicked.connect(lambda: self.stack.setCurrentIndex(1))
            p.btn_3d.clicked.connect(lambda: self.stack.setCurrentIndex(2))

        # ---- 摄像头悬浮窗 ----
        self.camera_widget = CameraWidget(self)
        self.camera_widget.setFixedSize(320, 240)
        self.camera_widget.show()

        # ---- 推理线程 ----
        self.inference_thread = InferenceThread(self.frame_buffer, self.recognizer)
        self.btn_camera_global = QPushButton("关闭摄像头", self)
        self.btn_camera_global.setFixedSize(90, 28)
        self.btn_camera_global.setFont(QFont("Microsoft YaHei", 10))
        self.btn_camera_global.setStyleSheet("QPushButton { background: rgba(255,255,255,0.7); border: 1px solid #aaa; border-radius: 6px; } QPushButton:hover { background: rgba(255,255,255,1); }")
        self.btn_camera_global.clicked.connect(self._toggle_camera)
        self.btn_camera_global.show()
        self.btn_camera_global.show()

        self.btn_settings_global = QPushButton("手势说明", self)
        self.btn_settings_global.setFixedSize(80, 28)
        self.btn_settings_global.setFont(QFont("Microsoft YaHei", 10))
        self.btn_settings_global.setStyleSheet("QPushButton { background: rgba(255,255,255,0.7); border: 1px solid #aaa; border-radius: 6px; } QPushButton:hover { background: rgba(255,255,255,1); }")
        self.btn_settings_global.clicked.connect(lambda: self.stack.setCurrentIndex(4))
        self.btn_settings_global.show()
        self.inference_thread.result_ready.connect(self._on_result)

        # ---- 手势 → HomePage 轮播 ----
        self.signal_gesture_action.connect(self._on_gesture_action)


        # ---- 去抖 ----
        self._last_gesture = None
        self._gesture_count = 0

    def _on_gesture_action(self, action: str):
        """手势操作分发到当前页面"""
        current = self.stack.currentIndex()
        home = self.pages["home"]
        if current == 0:  # 首页
            if action == "swipe_left":
                home._prev()
            elif action == "swipe_right":
                home._next()
        elif current == 2:
            viewer = self.pages["viewer"]
            if action == "zoom_in":
                viewer.zoom_in()
            elif action == "zoom_out":
                viewer.zoom_out()
            elif action == "circle":
                viewer.circle()

    def start(self):
        """启动摄像头和推理"""
        self.camera_widget.start(self.frame_buffer)
        self.inference_thread.start()

    def _go_detail(self):
        self.pages["detail"].reset_to_main()
        self.stack.setCurrentIndex(1)

    def _go_detail(self, index: int = 2):
        self.pages["detail"].set_project(index)
        self.pages["detail"].reset_to_main()
        self.stack.setCurrentIndex(1)
    def _toggle_camera(self):
        """切换摄像头开关"""
        home = self.pages["home"]
        if self.camera_widget._camera_thread and self.camera_widget._camera_thread._running:
            self.camera_widget.stop()
            self.camera_widget.hide()
            
            self.btn_camera_global.setText("打开摄像头")
        else:
            
            self.camera_widget.show()
            self.camera_widget.start(self.frame_buffer)
            self.btn_camera_global.setText("关闭摄像头")

    # ============================================================
    # 推理回调
    # ============================================================
    def _on_result(self, result: dict):
        gesture_idx = int(result["gesture"])
        confidence = result.get("confidence", 0)
        self.camera_widget.set_confidence(str(gesture_idx), confidence)
        control = index_to_control(gesture_idx)
        if control:
            self._on_control_gesture(control)

    # ============================================================
    # 手势 → 操作路由（根据当前页面）
    # ============================================================
    def _on_control_gesture(self, gesture: str):
        # 去抖：连续 CONSISTENCY_COUNT 次相同才触发
            
        if gesture == self._last_gesture:
            self._gesture_count += 1
        else:
            self._last_gesture = gesture
            self._gesture_count = 1
            return

        if self._gesture_count < config.CONSISTENCY_COUNT:
            return
        self._gesture_count = 0

        current = self.stack.currentIndex()
        current_name = {v: k for k, v in self.page_index.items()}[current]

        # 全局：palm 回到首页
        if gesture == "palm" and current != 0:
            self.stack.setCurrentIndex(0)
            return

        # 首页操作
        if current_name == "home":
            if gesture == "click":
                self._go_detail()
            elif gesture == "swipe_left":
                self.signal_gesture_action.emit("swipe_left")
            elif gesture == "swipe_right":
                self.signal_gesture_action.emit("swipe_right")

        # 详情页操作
        elif current_name == "detail":
            if gesture == "swipe_up":
                self.signal_gesture_action.emit("swipe_up")
            elif gesture == "swipe_down":
                self.signal_gesture_action.emit("swipe_down")

        # 3D 查看操作
        elif current_name == "viewer":
            if gesture in ("zoom_in", "zoom_out", "circle"):
                self.signal_gesture_action.emit(gesture)

    # ============================================================
    # 摄像头悬浮窗定位
    # ============================================================
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._position_camera()

    def _position_camera(self):
        w = self.camera_widget.width()
        h = self.camera_widget.height()
        self.camera_widget.setGeometry(self.width() - w - 20, 20, w, h)
        self.camera_widget.raise_()
        self.btn_camera_global.move(self.width() // 2 - 100, self.height() - 30)
        self.btn_camera_global.raise_()
        self.btn_settings_global.move(self.width() // 2 + 2, self.height() - 30)
        self.btn_settings_global.raise_()


    # ============================================================
    # 生命周期
    # ============================================================
    def closeEvent(self, event):
        self.inference_thread.stop()
        self.camera_widget.stop()
        event.accept()
