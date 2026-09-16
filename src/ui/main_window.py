"""主窗口"""
import time
from PySide6.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QStackedWidget,QPushButton
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QFont
from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer,InferenceThread
from src.core.gesture_mapper import index_to_control, CONTROL_CN
from src.ui.camera_widget import CameraWidget
from src.ui.home_page import HomePage
from src.ui.detail_page import DetailPage
from src.ui.viewer_page import ViewerPage
from src.ui.settings_page import SettingsPage
from src.ui.inheritor_page import InheritorPage
from src.ui.map_page import MapPage
from src import config

IDX={"inheritor":0,"home":1,"detail":2,"viewer":3,"settings":4,"map":5}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("非遗动态手势展示系统")
        self.resize(1280,800)
        self.frame_buffer=FrameBuffer()
        self.recognizer=GestureRecognizer()
        self.stack=QStackedWidget()
        self.pages={
            "inheritor":InheritorPage(),"home":HomePage(),"detail":DetailPage(),
            "viewer":ViewerPage(),"settings":SettingsPage(),"map":MapPage()
        }
        for p in self.pages.values(): self.stack.addWidget(p)
        self.stack.setCurrentIndex(1)
        central=QWidget(); central.setStyleSheet("background:transparent;")
        self.stack.setStyleSheet("background:transparent;")
        lo=QVBoxLayout(central); lo.setContentsMargins(0,0,0,0); lo.addWidget(self.stack)
        self.setCentralWidget(central)
        # 信号
        h=self.pages["home"]
        h.item_selected.connect(self._go_detail)
        h.go_inheritor.connect(self._enter_inheritor)
        h.go_map.connect(lambda:self.stack.setCurrentIndex(5))
        self.pages["detail"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["detail"].go_viewer.connect(lambda:self.stack.setCurrentIndex(3))
        self.pages["viewer"].go_home.connect(lambda:self.stack.setCurrentIndex(2))
        self.pages["settings"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["inheritor"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["map"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        # 摄像头
        self.cw=CameraWidget(self); self.cw.setFixedSize(320,240); self.cw.show()
        # 推理
        self.it=InferenceThread(self.frame_buffer,self.recognizer)
        self.it.result_ready.connect(self._on_result)
        # 全局按钮
        self.bc=QPushButton("关闭摄像头",self); self.bc.setFixedSize(90,28)
        self.bc.setFont(QFont("Microsoft YaHei",9))
        self.bc.setStyleSheet("QPushButton{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:8px;}QPushButton:hover{background:rgba(255,255,255,1);}")
        self.bc.clicked.connect(self._tc); self.bc.show()
        self.bs=QPushButton("手势说明",self); self.bs.setFixedSize(80,28)
        self.bs.setFont(QFont("Microsoft YaHei",9))
        self.bs.setStyleSheet("QPushButton{background:rgba(255,255,255,0.45);border:1px solid rgba(255,255,255,0.6);border-radius:8px;}QPushButton:hover{background:rgba(255,255,255,1);}")
        self.bs.clicked.connect(lambda:self.stack.setCurrentIndex(4)); self.bs.show()
        self._lg=None; self._gc=0
        self._cooldown_until=0.0   # 动作冷却截止时间(ms)
        self._locks=set()          # 已触发且未"松手"的动作（防重复触发）
        self._toast_until=0.0      # "已执行"提示截止时间(ms)
        self._toast_text=""
        # 显示保持状态
        self._disp_label=None; self._disp_conf=0.0; self._disp_ts=0.0
    def start(self):
        self.cw.start(self.frame_buffer); self.it.start()
    def _go_detail(self,i):
        self.pages["detail"].set_project(i); self.pages["detail"].reset_to_main()
        self.stack.setCurrentIndex(2)
    def _enter_inheritor(self):
        # 进入传承人页时默认选中"向下"按钮
        p=self.pages["inheritor"]; p._sel=0; p._apply_sel()
        self.stack.setCurrentIndex(0)
    def _tc(self):
        if self.cw._camera_thread and self.cw._camera_thread._running:
            self.cw.stop(); self.cw.hide(); self.bc.setText("打开摄像头")
            # 清空缓冲：关摄像头后推理线程不再拿旧帧预测
            self.frame_buffer.clear()
            self.recognizer._prob_win.clear()
        else:
            self.frame_buffer.clear()
            self.recognizer._prob_win.clear()
            self.cw.show(); self.cw.start(self.frame_buffer); self.bc.setText("关闭摄像头")
    def _on_result(self,r):
        # 显示用即时(未平滑)结果 —— 切换手势时立刻跟手
        dg=int(r.get("raw_gesture", r["gesture"])); dc=r.get("raw_confidence", r.get("confidence",0))
        now=time.time()*1000.0
        # 松手判定：即时置信低于显示门槛 → 解锁所有动作，并重置去抖
        # （要求重新做出手势才能再触发，避免用残留的平滑结果重复触发）
        if dc < config.DISPLAY_CONFIDENCE:
            self._locks.clear()
            self._lg=None; self._gc=0
        # "已执行"提示优先显示
        if now < self._toast_until:
            self.cw.set_custom(self._toast_text)
        else:
            cur=self._disp_label
            # 允许更新显示的条件：达到显示门槛，且（当前无显示 / 同一个手势 / 新结果置信足够高才抢走）
            if dc >= config.DISPLAY_CONFIDENCE and (cur is None or str(dg)==cur or dc >= config.DISPLAY_SWITCH_CONFIDENCE):
                self._disp_label=str(dg); self._disp_conf=dc; self._disp_ts=now
                self.cw.set_confidence(str(dg), dc)
            elif cur is not None and (now - self._disp_ts) < config.DISPLAY_HOLD_MS:
                # 保持当前显示（动态手势结束后不立刻变/不被中等置信错误类抢走）
                self.cw.set_confidence(cur, self._disp_conf)
            else:
                self._disp_label=None
                self.cw.set_confidence(None, dc)
        # 触发用平滑结果 —— 保持稳定，避免误触发
        gid=int(r["gesture"]); cf=r.get("confidence",0)
        if cf < config.CONFIDENCE_THRESHOLD:
            return
        c=index_to_control(gid)
        if c: self._ocg(c)
    def _ocg(self,g):
        now=time.time()*1000.0
        # 冷却：触发一次动作后，冷却期内不再响应
        if now < self._cooldown_until:
            return
        # 去抖：连续 N 次相同动作才触发
        if g==self._lg: self._gc+=1
        else: self._lg=g; self._gc=1; return
        if self._gc<config.CONSISTENCY_COUNT: return
        self._gc=0
        # 锁存：该动作已执行且用户尚未松手 → 不重复触发
        if g in self._locks:
            return
        self._locks.add(g)
        self._cooldown_until = now + config.ACTION_COOLDOWN_MS
        # "已执行"提示（立即显示，约 0.8s 后恢复）
        self._toast_until = now + config.TOAST_MS
        self._toast_text = "✔ 已执行：" + CONTROL_CN.get(g, g)
        self.cw.set_custom(self._toast_text)
        cn={v:k for k,v in IDX.items()}[self.stack.currentIndex()]
        if cn=="home":
            if g=="click": self._go_detail(self.pages["home"].current_index())
            elif g=="swipe_left": self.pages["home"]._prev()
            elif g=="swipe_right": self.pages["home"]._next()
        elif cn=="detail":
            if g=="swipe_left": self.pages["detail"].select_prev()
            elif g=="swipe_right": self.pages["detail"].select_next()
            elif g=="click": self.pages["detail"].activate_selected()
        elif cn=="viewer":
            v=self.pages["viewer"]
            if g=="zoom_in": v.zoom_in()
            elif g=="zoom_out": v.zoom_out()
            elif g=="circle": v.circle()
        elif cn=="inheritor":
            p=self.pages["inheritor"]
            if g=="swipe_left": p.select_prev()          # 左/右切换选中[向下,返回]
            elif g=="swipe_right": p.select_next()
            elif g=="swipe_down": p._next()              # 向下抛出 = 直接翻下一位
            elif g=="click": p.activate_selected()       # 点击 = 确认选中按钮
        elif cn=="map":
            p=self.pages["map"]
            if g=="swipe_left": p.select_prev()
            elif g=="swipe_right": p.select_next()
            elif g=="zoom_in": p.zoom_in()               # 张开两次 → 地图放大
            elif g=="zoom_out": p.zoom_out()             # 握拳(缩小) → 地图缩小
            elif g=="click": p.activate_selected()       # 确认"返回"
    def resizeEvent(self,e):
        super().resizeEvent(e)
        self.cw.setGeometry(self.width()-340,20,320,240); self.cw.raise_()
        self.bc.move(self.width()//2-100,self.height()-30); self.bc.raise_()
        self.bs.move(self.width()//2+2,self.height()-30); self.bs.raise_()
    def closeEvent(self,e):
        self.it.stop(); self.cw.stop(); e.accept()
