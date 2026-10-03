"""主窗口"""
import time
from PySide6.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QStackedWidget,QPushButton
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QFont
from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer,InferenceThread
from src.core.gesture_mapper import index_to_control, CONTROL_CN
from src.core import project_assets
from src.ui.camera_widget import CameraWidget
from src.ui.home_page import HomePage
from src.ui.detail_page import DetailPage
from src.ui.viewer_page import ViewerPage
from src.ui.settings_page import SettingsPage
from src.ui.inheritor_page import InheritorPage
from src import config

IDX={"inheritor":0,"home":1,"detail":2,"viewer":3,"settings":4}

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
            "viewer":ViewerPage(),"settings":SettingsPage()
        }
        for p in self.pages.values(): self.stack.addWidget(p)
        self.stack.setCurrentIndex(1)
        # 手势状态（必须在 currentChanged 连接之前初始化）
        self._lg=None; self._gc=0
        # ---- 动作冷却（现在**唯一**的防重复触发机制）----
        # 分两步走：动作执行后先 `_pending_release=True`，**等访客松手**；
        # 松手那一刻才把 `_cooldown_until` 定下来。为什么要分两步见 _on_result。
        self._pending_release=False
        self._cooldown_until=0.0
        self._hold_since=0.0       # 上次执行动作的时刻(ms)，只给 MAX_HOLD_MS 防死锁用
        self._toast_until=0.0      # "已执行"提示截止时间(ms)
        self._toast_text=""
        self._disp_label=None; self._disp_conf=0.0; self._disp_ts=0.0  # 显示保持状态
        # 换页：重置去抖（冷却要保留，理由见 _on_page_changed）
        self.stack.currentChanged.connect(self._on_page_changed)
        central=QWidget(); central.setStyleSheet("background:transparent;")
        self.stack.setStyleSheet("background:transparent;")
        lo=QVBoxLayout(central); lo.setContentsMargins(0,0,0,0); lo.addWidget(self.stack)
        self.setCentralWidget(central)
        # 信号
        h=self.pages["home"]
        h.item_selected.connect(self._go_detail)
        h.go_inheritor.connect(self._enter_inheritor)
        self.pages["detail"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["detail"].go_viewer.connect(self._go_viewer)
        self.pages["viewer"].go_home.connect(lambda:self.stack.setCurrentIndex(2))
        self.pages["settings"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["inheritor"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
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
    def _on_page_changed(self, idx):
        # 重置去抖：新页面上要重新攒够连续次数。
        #
        # 但**不要动冷却**——这里曾经清过（当年清的是"锁存"），结果正好帮了倒忙：
        # 换页那一刻，用户的手通常还停在触发手势的姿势上（尤其是单击后慢松手），
        # 防护一清，残留手势几秒后就在新页面上又触发一次
        # （首页单击进详情 → 残留单击又被详情页当"确认" → 直接弹回首页）。
        # 防护应该跟着"手"走：由**松手**释放，见 _on_result。
        self._lg=None; self._gc=0
        # 摄像头悬浮窗始终置顶（页面内容若与它重叠，以摄像头为准）
        self.cw.raise_(); self.bc.raise_(); self.bs.raise_()
    def start(self):
        self.cw.start(self.frame_buffer)
        # 权重不可用时不启动推理：随机权重的输出看着"很正常"，
        # 与其在展台上放一堆错误手势，不如只留摄像头预览、用鼠标操作。
        if self.recognizer.status == "ok":
            self.it.start()
        else:
            print(f"[Main] 权重状态={self.recognizer.status}，手势识别未启用", flush=True)
    def _go_detail(self,i):
        self.pages["detail"].set_project(i); self.pages["detail"].reset_to_main()
        self.stack.setCurrentIndex(2)
    def _go_viewer(self):
        # 进入 3D 页时加载当前项目的模型
        slug = project_assets.slug_of(self.pages["detail"]._pi)
        self.pages["viewer"].load_model(slug)
        self.stack.setCurrentIndex(3)
    def _enter_inheritor(self):
        self.stack.setCurrentIndex(0)
    def _tc(self):
        # 判据是"线程还在不在"，不是 _running —— 线程刚启动时 _running 可能还没置位，
        # 那样按钮状态会和实际相反（点一下变成"又开一次"）
        if self.cw._camera_thread is not None:
            self.cw.stop(); self.cw.hide(); self.bc.setText("打开摄像头")
            # 清空缓冲：关摄像头后推理线程不再拿旧帧预测
            self.frame_buffer.clear()
            self.recognizer.reset_smoothing()
        else:
            self.frame_buffer.clear()
            self.recognizer.reset_smoothing()
            self.it.mark_active()          # 重开摄像头：空闲计时清零，马上回全速档
            self.cw.show(); self.cw.start(self.frame_buffer)
            self.bc.setText("关闭摄像头")
    def _on_result(self,r):
        # 显示用即时(未平滑)结果 —— 切换手势时立刻跟手
        dg=int(r.get("raw_gesture", r["gesture"])); dc=r.get("raw_confidence", r.get("confidence",0))
        now=time.time()*1000.0
        # 松手判定：即时置信低于「松手门槛」→ 认为访客把手放下了。
        # **这一刻才是冷却开始计时的时刻**（不是动作执行的时刻）：
        # 若从执行时刻起算，冷却 1.5s 一到、手还举着，残留手势就会被当成第二次操作
        # —— 正是 §1.5 那个坑（首页点进详情 → 被弹回首页）。
        # ⚠ 用的是独立的 RELEASE_CONFIDENCE，**不是** DISPLAY_CONFIDENCE ——
        # 显示门槛按观感调（现在为了不闪，它比松手门槛高），而松手门槛是防护线；
        # 两者联动的话，调观感会悄悄削弱防护。
        if dc < config.RELEASE_CONFIDENCE:
            if self._pending_release:
                self._cooldown_until = now + config.ACTION_COOLDOWN_MS
                self._pending_release = False
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
        # ============ 现在只剩一道机制：动作冷却 ============
        # 前半段：动作已执行、还在等访客松手 → 一律不响应。
        # （这正是原先"锁存"挡的那个场景，换页之后尤其重要，见 _on_page_changed）
        if self._pending_release:
            # 防死锁：万一模型对静止画面一直报同一个手势，就永远等不到"松手"。
            # 超过 MAX_HOLD_MS 强制起算冷却 —— 宁可偶尔多触发一次，
            # 也不能让整个展台对任何手势都没反应（那种坏法不报错、看着一切正常）。
            if (now - self._hold_since) >= config.MAX_HOLD_MS:
                self._pending_release = False
                self._cooldown_until = now + config.ACTION_COOLDOWN_MS
            else:
                return
        # 后半段：访客已松手，冷却期内不再响应
        if now < self._cooldown_until:
            return
        # 去抖：连续 N 次相同动作才触发。默认 N=1 → 一次即触发。
        # ⚠ 这里**不能**像原来那样在"手势变了"那一支直接 return ——
        # 那样第一次永远轮不到触发，N=1 就变成了空转。
        if g==self._lg: self._gc+=1
        else: self._lg=g; self._gc=1
        if self._gc<config.CONSISTENCY_COUNT: return
        self._gc=0
        # 执行了动作 → 进入"等松手"状态。冷却**此刻还不起算**，
        # 要等 _on_result 判定松手（或 MAX_HOLD_MS 兜底）才开始计时。
        self._pending_release = True
        self._hold_since = now
        self._cooldown_until = 0.0
        # 到这里闸门都过了，动作**真的会执行** → 告诉推理线程"有人在用"，
        # 让它回到全速档。这就是空闲降频的判据（见 docs/MECHANISMS.md §2.2）。
        # ⚠ 判据刻意是"执行过动作"而不是"模型输出了高置信手势"：访客路过就会产生
        # 高分样本（实测走路有 15.5% 的采样 ≥0.8），用后者的话空闲计时永远被清零。
        self.it.mark_active()
        cn={v:k for k,v in IDX.items()}[self.stack.currentIndex()]
        # "已执行"提示（立即显示，约 0.8s 后恢复）；视频页的左/右实际是快退/快进
        label = CONTROL_CN.get(g, g)
        if g in ("swipe_left","swipe_right") and (
                cn=="inheritor" or (cn=="detail" and self.pages["detail"].is_video_view())):
            label = "快退" if g=="swipe_left" else "快进"
        self._toast_until = now + config.TOAST_MS
        self._toast_text = "✔ 已执行：" + label
        self.cw.set_custom(self._toast_text)
        if cn=="home":
            if g=="click": self._go_detail(self.pages["home"].current_index())
            elif g=="swipe_left": self.pages["home"]._prev()
            elif g=="swipe_right": self.pages["home"]._next()
        elif cn=="detail":
            d=self.pages["detail"]
            if d.is_video_view():
                # 非遗详情子页：左/右 = 视频快退/快进，点击 = 返回主视图
                if g=="swipe_left": d.seek(-config.SEEK_STEP_MS)
                elif g=="swipe_right": d.seek(config.SEEK_STEP_MS)
                elif g=="click": d.activate_selected()
            else:
                if g=="swipe_left": d.select_prev()
                elif g=="swipe_right": d.select_next()
                elif g=="click": d.activate_selected()
        elif cn=="viewer":
            v=self.pages["viewer"]
            if g=="zoom_in": v.zoom_in()
            elif g=="zoom_out": v.zoom_out()
            elif g=="circle": v.circle()
            elif g=="click": v.activate_selected()   # 确认"返回"
        elif cn=="inheritor":
            p=self.pages["inheritor"]
            if g=="swipe_left": p.seek_back()            # 左/右 = 视频快退/快进
            elif g=="swipe_right": p.seek_forward()
            elif g=="swipe_down": p.next_person()        # 向下抛出 = 下一位
            elif g=="swipe_up": p.prev_person()          # 向上抛出 = 上一位
            elif g=="click": p.confirm()                 # 点击 = 返回
    def resizeEvent(self,e):
        super().resizeEvent(e)
        self.cw.setGeometry(self.width()-340,20,320,240); self.cw.raise_()
        self.bc.move(self.width()//2-100,self.height()-30); self.bc.raise_()
        self.bs.move(self.width()//2+2,self.height()-30); self.bs.raise_()
    def closeEvent(self,e):
        self.it.stop(); self.cw.stop(); e.accept()
