"""主窗口"""
from PySide6.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QStackedWidget,QLabel,QPushButton
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QFont
from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer,InferenceThread
from src.core.gesture_mapper import index_to_control
from src.ui.camera_widget import CameraWidget
from src.ui.home_page import HomePage
from src.ui.detail_page import DetailPage
from src.ui.viewer_page import ViewerPage
from src.ui.settings_page import SettingsPage
from src.ui.inheritor_page import InheritorPage
from src import config

class MainWindow(QMainWindow):
    signal_gesture_action=Signal(str)
    def __init__(self):
        super().__init__()
        self.setWindowTitle("非遗动态手势展示系统")
        self.resize(1280,800)
        self.frame_buffer=FrameBuffer()
        self.recognizer=GestureRecognizer()
        self.stack=QStackedWidget()
        self.pages={}
        self.pages["inheritor"]=InheritorPage()
        self.pages["home"]=HomePage()
        self.pages["detail"]=DetailPage()
        self.pages["viewer"]=ViewerPage()
        self.pages["settings"]=SettingsPage()
        self.page_index={"inheritor":0,"home":1,"detail":2,"viewer":3,"settings":4}
        for p in self.pages.values(): self.stack.addWidget(p)
        self.stack.setCurrentIndex(1)
        central=QWidget()
        central.setStyleSheet("background: transparent;")
        self.stack.setStyleSheet("background: transparent;")
        layout=QVBoxLayout(central)
        layout.setContentsMargins(0,0,0,0)
        layout.addWidget(self.stack)
        self.setCentralWidget(central)
        # 信号连接
        self.pages["home"].item_selected.connect(self._go_detail)
        self.pages["home"].go_inheritor.connect(lambda:self.stack.setCurrentIndex(0))
        self.pages["detail"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["detail"].go_viewer.connect(lambda:self.stack.setCurrentIndex(3))
        self.pages["viewer"].go_home.connect(lambda:self.stack.setCurrentIndex(2))
        self.pages["settings"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["inheritor"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.signal_gesture_action.connect(self._on_gesture_action)
        # 摄像头
        self.camera_widget=CameraWidget(self)
        self.camera_widget.setFixedSize(320,240)
        self.camera_widget.show()
        # 推理线程
        self.inference_thread=InferenceThread(self.frame_buffer,self.recognizer)
        self.inference_thread.result_ready.connect(self._on_result)
        # 全局按钮
        self.btn_cam=QPushButton("关闭摄像头",self)
        self.btn_cam.setFixedSize(90,28)
        self.btn_cam.setFont(QFont("Microsoft YaHei",9))
        self.btn_cam.setStyleSheet("QPushButton{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:8px;}QPushButton:hover{background:rgba(255,255,255,1);}")
        self.btn_cam.clicked.connect(self._toggle_camera)
        self.btn_cam.show()
        self.btn_set=QPushButton("手势说明",self)
        self.btn_set.setFixedSize(80,28)
        self.btn_set.setFont(QFont("Microsoft YaHei",9))
        self.btn_set.setStyleSheet("QPushButton{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:8px;}QPushButton:hover{background:rgba(255,255,255,1);}")
        self.btn_set.clicked.connect(lambda:self.stack.setCurrentIndex(4))
        self.btn_set.show()
        self._last_gesture=None; self._gesture_count=0

    def start(self):
        self.camera_widget.start(self.frame_buffer)
        self.inference_thread.start()
    def _go_detail(self,index=2):
        self.pages["detail"].set_project(index)
        self.pages["detail"].reset_to_main()
        self.stack.setCurrentIndex(2)
    def _toggle_camera(self):
        if self.camera_widget._camera_thread and self.camera_widget._camera_thread._running:
            self.camera_widget.stop(); self.camera_widget.hide()
            self.btn_cam.setText("打开摄像头")
        else:
            self.camera_widget.show(); self.camera_widget.start(self.frame_buffer)
            self.btn_cam.setText("关闭摄像头")
    def _on_result(self,result:dict):
        gid=int(result["gesture"])
        conf=result.get("confidence",0)
        self.camera_widget.set_confidence(str(gid),conf)
        ctrl=index_to_control(gid)
        if ctrl: self._on_control_gesture(ctrl)
    def _on_control_gesture(self,g:str):
        if g==self._last_gesture: self._gesture_count+=1
        else: self._last_gesture=g; self._gesture_count=1; return
        if self._gesture_count<config.CONSISTENCY_COUNT: return
        self._gesture_count=0
        cur=self.stack.currentIndex()
        cn={v:k for k,v in self.page_index.items()}[cur]
        if g=="palm" and cur!=1: self.stack.setCurrentIndex(1); return
        if cn=="home":
            if g=="click": self._go_detail()
            elif g in("swipe_left","swipe_right"): self.signal_gesture_action.emit(g)
        elif cn=="detail":
            if g in("swipe_up","swipe_down"): self.signal_gesture_action.emit(g)
        elif cn=="viewer":
            if g in("zoom_in","zoom_out","circle"): self.signal_gesture_action.emit(g)
    def _on_gesture_action(self,action:str):
        cur=self.stack.currentIndex()
        home=self.pages["home"]
        if cur==1:
            if action=="swipe_left": home._prev()
            elif action=="swipe_right": home._next()
        elif cur==3:
            viewer=self.pages["viewer"]
            if action=="zoom_in": viewer.zoom_in()
            elif action=="zoom_out": viewer.zoom_out()
            elif action=="circle": viewer.circle()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        w,h=320,240
        self.camera_widget.setGeometry(self.width()-w-20,20,w,h)
        self.camera_widget.raise_()
        self.btn_cam.move(self.width()//2-100,self.height()-30)
        self.btn_cam.raise_()
        self.btn_set.move(self.width()//2+2,self.height()-30)
        self.btn_set.raise_()
    def closeEvent(self,event):
        self.inference_thread.stop()
        self.camera_widget.stop()
        event.accept()
