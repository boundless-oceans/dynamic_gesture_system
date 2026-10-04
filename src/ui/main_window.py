"""主窗口"""
import time
from PySide6.QtWidgets import QMainWindow,QWidget,QVBoxLayout,QStackedWidget,QPushButton
from PySide6.QtCore import Qt,Signal
from PySide6.QtGui import QFont
from src.core.frame_buffer import FrameBuffer
from src.core.inference import GestureRecognizer,InferenceThread
from src.core.static_gesture import StaticGestureRecognizer, action_for as static_action
from src.core.gesture_mapper import index_to_control, CONTROL_CN, STATIC_YIELD_ON_PAGE
from src.core.like_store import LikeStore
from src.core.project_data import INHERITORS
from src.core import project_assets
from src.ui.camera_widget import CameraWidget
from src.ui.home_page import HomePage
from src.ui.detail_page import DetailPage
from src.ui.viewer_page import ViewerPage
from src.ui.settings_page import SettingsPage
from src.ui.inheritor_page import InheritorPage
from src.ui.toast import ToastOverlay
from src.ui.page_fade import PageFade
from src.ui.base_page import BasePage
from src import config

IDX={"inheritor":0,"home":1,"detail":2,"viewer":3,"settings":4}

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("非遗动态手势展示系统")
        self.resize(1280,800)
        self.frame_buffer=FrameBuffer()
        self.recognizer=GestureRecognizer()
        # 静态手势模型（认"手此刻的形状"）。权重缺失时 status != "ok"，
        # 整条路自动静默跳过 —— 动态手势不受任何影响
        self.static=StaticGestureRecognizer()
        # 点赞计数（按非遗项目 / 传承人分记，见 src/core/like_store.py）
        self.likes=LikeStore()
        self.stack=QStackedWidget()
        self.pages={
            "inheritor":InheritorPage(),"home":HomePage(),"detail":DetailPage(),
            "viewer":ViewerPage(),"settings":SettingsPage()
        }
        for p in self.pages.values(): self.stack.addWidget(p)
        self.stack.setCurrentIndex(1)
        # 手势状态（必须在 currentChanged 连接之前初始化）
        self._lg=None; self._gc=0
        # ---- 防重复触发：两道，都很短，且都不依赖机器快慢 ----
        # ① 冷却：从**触发**时刻起算，ACTION_COOLDOWN_MS 内不再响应
        self._cooldown_until=0.0
        # ② 间隙：触发条件必须**先不成立一次**，下一次才算数。
        #    这就是"同一个手势一直被识别"不会重复触发的保证（§1.5 的精确防护）——
        #    判定在 _on_result 里，用的是触发用的同一个量（平滑置信度）。
        self._need_gap=False
        self._hold_since=0.0       # 上次触发时刻(ms)，只给 MAX_HOLD_MS 防死锁用
        # 静态手势是**另一条通道**，间隙和去抖都各管各的（理由见 _on_static / _ocg）
        self._static_need_gap=False
        self._static_lg=None; self._static_count=0
        self._toast_text=""        # 最近一次"已执行"的文案（显示由 self.toast 负责）
        self._disp_label=None; self._disp_conf=0.0; self._disp_ts=0.0  # 显示保持状态
        # 换页：重置去抖（冷却要保留，理由见 _on_page_changed）
        self.stack.currentChanged.connect(self._on_page_changed)
        central=QWidget(); central.setStyleSheet("background:transparent;")
        self.stack.setStyleSheet("background:transparent;")
        lo=QVBoxLayout(central); lo.setContentsMargins(0,0,0,0); lo.addWidget(self.stack)
        self.setCentralWidget(central)
        # 换页过渡层：挂在**页面容器**上（不是主窗口），这样它只盖住页面，
        # 不会盖住右上角的摄像头悬浮窗
        self.fade=PageFade(central)
        self._prev_idx=self.stack.currentIndex()   # 上一页是谁，换页时靠它取快照
        # 信号
        h=self.pages["home"]
        h.item_selected.connect(self._go_detail)              # 项目卡 → 详情页
        h.inheritor_selected.connect(self._enter_inheritor)   # 传承人卡 → 传承人页那一位
        self.pages["detail"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["detail"].go_viewer.connect(self._go_viewer)
        self.pages["viewer"].go_home.connect(lambda:self.stack.setCurrentIndex(2))
        self.pages["settings"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        self.pages["inheritor"].go_home.connect(lambda:self.stack.setCurrentIndex(1))
        # 摄像头
        self.cw=CameraWidget(self); self.cw.setFixedSize(320,240); self.cw.show()
        # 操作提示（屏幕下方居中）。建在摄像头之后，免得被它盖住
        self.toast=ToastOverlay(self)
        # 推理
        self.it=InferenceThread(self.frame_buffer,self.recognizer,self.static)
        self.it.result_ready.connect(self._on_result)
        # 粒子背景跟着"空闲多久"降频（必须等 it 建好之后）
        self._wire_idle_source()
        # 首页卡片上的点赞角标（页面自己来取，见 HomePage.set_like_source）
        self.pages["home"].set_like_source(self._like_count_for)
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
        # 但**不要动冷却、也不要动"间隙"状态**——这里曾经清过（当年清的是"锁存"），
        # 结果正好帮了倒忙：换页那一刻，用户的手通常还停在触发手势的姿势上
        # （尤其是单击后慢松手），防护一清，残留手势几秒后就在新页面上又触发一次
        # （首页单击进详情 → 残留单击又被详情页当"确认" → 直接弹回首页）。
        # 防护跟着"手"走，不跟着页面走：间隙由手势**离开**来释放，见 _on_result。
        self._lg=None; self._gc=0
        # 换页过渡：取**旧页面**的快照盖上去再淡出（硬切 → 交叉淡入淡出）。
        # 必须在这里取：currentChanged 是**切完之后**才发的，旧页面此刻已经隐藏，
        # 但 QWidget.grab() 走的是 render()，与可见性无关
        # （实测验证过，拿到的仍是旧页面自己的内容）。
        old=self.stack.widget(self._prev_idx)
        if old is not None and self._prev_idx!=idx:
            self.fade.start(old.grab())
        self._prev_idx=idx
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
    def _wire_idle_source(self):
        """把"已经空闲多久(ms)"的取值函数交给各带粒子背景的页面。

        粒子是**整页重绘**，空馆时没人看，没必要还按 20fps 刷。
        空闲的判据交给推理线程 —— 它本来就在记"最近一次真的执行了动作是什么时候"
        （见 docs/MECHANISMS.md §2.2），不用另起一套。

        设置页不是 BasePage（自己是画背景的），没有粒子，跳过。
        """
        for p in self.pages.values():
            if isinstance(p, BasePage):
                p.set_idle_source(self.it.idle_ms)
    def _enter_inheritor(self, index=0):
        # 首页第二排每位传承人各是一张卡，点哪张就该进哪一位。
        # 原先没有这个参数，从首页进来**永远停在第一位**。
        self.pages["inheritor"].show_person(index)
        self.stack.setCurrentIndex(IDX["inheritor"])
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
        # 悬浮窗**始终显示识别结果**。"已执行"提示已搬到屏幕下方居中
        # （src/ui/toast.py）—— 两者各说各的，访客既看得到模型认出了什么，
        # 也看得到系统执行了什么，比原来"提示期间把识别结果顶掉"更有信息量。
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
        # ---- 静态手势（架构 A：只做加法）----
        # ⚠ 放在动态那一段**之前**，而且**不 return** —— 这一路只对 ok / 比耶说话，
        #   判成别的类就是弃权，动态照常走。
        st=r.get("static")
        if st is None:
            self.cw.set_static(None,0.0)
        else:
            self.cw.set_static(st.get("label"),st.get("confidence",0.0))
        self._on_static(st)
        # 触发用平滑结果 —— 保持稳定，避免误触发
        gid=int(r["gesture"]); cf=r.get("confidence",0)
        if cf < config.CONFIDENCE_THRESHOLD:
            # 触发条件**不成立**了 —— 这就是"间隙"。
            # 它是"同一个手势一直被识别"与"访客真的把手放下了"之间的分界线：
            # 前者平滑置信度一直在门槛之上，间隙永远不来，于是不会重复触发（§1.5）；
            # 后者一掉下来就记上，下一个手势立刻能触发。
            #
            # ⚠ 刻意用**平滑**置信度、且是**触发用的同一个门槛**：触发看哪个量，
            #   间隙就得看哪个量。原先用"即时置信度 < RELEASE_CONFIDENCE(0.35)"是错配
            #   —— 门槛低得多、时机也对不上：手放下了模型仍可能对残留画面报 0.4~0.6，
            #   于是永远等不到间隙，一路走到 MAX_HOLD_MS 兜底（实测就是"要等好久"）。
            self._need_gap = False
            self._lg=None; self._gc=0
            return
        c=index_to_control(gid)
        if c: self._ocg(c)
    def _page_name(self):
        """当前页面名（IDX 的反查）。"""
        return {v: k for k, v in IDX.items()}.get(self.stack.currentIndex())
    # ---- 点赞：给"当前这个非遗项目 / 传承人"记一次 ----
    #
    # 键的形态是 `proj:<slug>` / `inh:<姓名>`。带前缀有两个用处：
    # 一眼能看出这一条是项目还是人；也免得将来某个人名正好撞上某个 slug。
    #
    # ⚠ **键必须稳定**，否则点赞数会**悄悄串到别人身上**（不报错，最难发现）：
    #   * 项目用 **slug**（`baogong` 这种），**不是序号** ——
    #     序号会随项目增减 / 调序全体错位
    #   * 传承人用 **姓名** —— 全代码里认传承人本来就是用 name
    #     （见 project_assets.inheritor_video / inheritor_photo），没有别的标识
    @staticmethod
    def _like_key(kind, idx) -> str:
        if kind == "project":
            slug = project_assets.slug_of(idx)
            return ("proj:" + slug) if slug else ""
        if kind == "inheritor" and 0 <= idx < len(INHERITORS):
            name = INHERITORS[idx].get("name") or ""
            return ("inh:" + name) if name else ""
        return ""

    def _current_like_key(self) -> str:
        """此刻"可点赞的对象"的键；**当前页面上没有这样的对象时返回空串**。

        首页两排都是卡片，所以两排都能点赞（用户 2026-10-04 定的 B 方案）——
        第一排是非遗项目、第二排是传承人，各自记各自的。
        """
        cn = self._page_name()
        if cn == "home":
            kind, idx = self.pages["home"].current_target()
            return self._like_key(kind, idx)
        if cn == "inheritor":
            return self._like_key("inheritor", self.pages["inheritor"]._index)
        if cn == "detail":
            return self._like_key("project", self.pages["detail"]._pi)
        if cn == "viewer":
            # 3D 页记着自己加载的是哪个模型（load_model 时存下的）
            slug = self.pages["viewer"]._slug
            return ("proj:" + slug) if slug else ""
        return ""            # 设置页上没有可点赞的对象

    def _like_count_for(self, kind, idx) -> int:
        """首页卡片角标来问"这一张有多少赞"（拉模式，见 HomePage.set_like_source）"""
        key = self._like_key(kind, idx)
        return self.likes.count(key) if key else 0

    def _count_like(self, key) -> str:
        """给 key 记一次赞，返回提示文案。只在 key 非空时被调用。"""
        n = self.likes.add(key)
        # 首页角标立刻跟上（它自己是拉模式的，得有人叫它一声）
        self.pages["home"].refresh_likes()
        return "点赞（共 %d 次）" % n
    def _static_yields_here(self,action):
        """这个静态动作在当前页面要不要**让位给动态模型**。

        只有一个原因：**手型撞车**。两个模型吃同一块画面，同一个手型会同时喂进
        两边。"比耶"（✌️）撞的是动态的「双指指向 / 双指双击 → 旋转模型」，
        而那个动作**只在 3D 页上有效** —— 所以 3D 页把 ✌️ 归动态模型
        （设置页那张表里，3D 页的"旋转模型"本来就写着用两指）。

        别的页面上动态那个手势本来就是空转，所以只在 3D 页让位。
        让位时按"条件不成立"处理（顺带把间隙记上），换到别的页面还能正常用。
        """
        return STATIC_YIELD_ON_PAGE.get(action)==self._page_name()
    def _on_static(self,st):
        """静态手势通道（架构 A：**只做加法**）。

        只对**绑定的那两个类**（ok / 比耶）说话；判成别的类一律**弃权** ——
        动态模型照旧、不受任何影响。所以这个模型判错绝大多数类时产生不了后果。
        """
        if st is None:
            # 没有静态结果（权重缺失 / 这一路出错）→ 当作"条件不成立"处理，
            # 免得它一旦恢复反而被旧状态挡住
            self._static_need_gap=False; self._static_lg=None; self._static_count=0
            return
        action=static_action(st.get("label"),st.get("confidence",0.0))
        if action is not None and self._static_yields_here(action):
            action=None            # 这一页上这个手型归动态模型 → 静态弃权
        if action is None:
            # 触发条件**不成立**了（不是绑定的类，或没够门槛）——
            # 这就是**静态通道自己的间隙**：姿势一松开就记上，下次才允许再触发。
            # ⚠ 这一条是"举着 OK 不动不会一直回首页"的唯一保证。
            self._static_need_gap=False
            self._static_lg=None; self._static_count=0
            return
        # 连续 STATIC_CONSISTENCY 帧都判成同一个绑定动作才触发。
        # 静态姿势是**被保持**的，多等一帧几乎不花钱，而单帧的误判会被挡掉。
        if action==self._static_lg: self._static_count+=1
        else: self._static_lg=action; self._static_count=1
        if self._static_count<config.STATIC_CONSISTENCY: return
        self._ocg(action,source="static")
    def _ocg(self,g,source="dynamic"):
        # 点赞得有个"可点赞的对象"才做得成（设置页上就没有）。
        # ⚠ 没有就**在这里直接返回，连冷却都不消耗** —— 否则访客在设置页比个大拇指
        #   会白白静默 1.5 秒，而且提示胶囊还会谎报"已执行：点赞"。
        #   这和"到了边界不响应"那种是两回事：那种确实执行了一次无效动作，
        #   这种是**根本没有作用对象**。
        like_key = self._current_like_key() if g=="like" else ""
        if g=="like" and not like_key: return
        now=time.time()*1000.0
        # ============ 防重复触发：两道，都很短，且都不依赖机器快慢 ============
        # ① 间隙：上次触发之后，触发条件还没"断"过 → 不响应。
        #
        # ⚠ **两条通道各管各的间隙**，判据不同、绝不能合用：
        #     动态看"平滑置信度有没有掉下 CONFIDENCE_THRESHOLD"（判定在 _on_result）
        #     静态看"那个姿势有没有松开"（判定在 _on_static）
        #   合用会互相锁死 —— 举个真实的：比完 OK 手还没放下，动态模型很可能
        #   持续报 B0A 单指指向（OK 的手型里就有那根伸出的食指），于是动态那条
        #   间隙永远等不来，访客想接着翻页最长被憋 MAX_HOLD_MS 3 秒。
        if source=="static":
            if self._static_need_gap:
                return
        elif self._need_gap:
            # 防死锁：万一模型对静止画面一直报同一个手势、门槛之上不下来，
            # 就永远等不到间隙。超过 MAX_HOLD_MS 强制放行 —— 宁可偶尔多触发一次，
            # 也不能让整个展台对任何手势都没反应（那种坏法不报错、看着一切正常）。
            #
            # ⚠ 静态通道**没有**这一层，也不需要：举着一个姿势不动本来就该只触发
            #   一次（间隙要求的是"松手"，那个条件访客完全控制得了）。
            if (now - self._hold_since) >= config.MAX_HOLD_MS:
                self._need_gap = False
                self._cooldown_until = now + config.ACTION_COOLDOWN_MS
            else:
                return
        # ② 冷却：从**触发**时刻起算。**两条通道共用** —— 一次只执行一个动作，
        #    "刚比完 OK 就抛一下"不该两个都生效。
        if now < self._cooldown_until:
            return
        # 去抖：连续 N 次相同动作才触发。默认 N=1 → 一次即触发。
        # ⚠ 这里**不能**像原来那样在"手势变了"那一支直接 return ——
        # 那样第一次永远轮不到触发，N=1 就变成了空转。
        #
        # ⚠ **静态通道不走这里**：它有自己的"连续 STATIC_CONSISTENCY 帧"计数
        #   （见 _on_static），而 _lg/_gc 是动态通道的状态，混进来会互相清零。
        if source=="dynamic":
            if g==self._lg: self._gc+=1
            else: self._lg=g; self._gc=1
            if self._gc<config.CONSISTENCY_COUNT: return
            self._gc=0
        # 执行了动作 → 冷却**从这一刻起算**，并要求一个"间隙"才允许下次触发
        self._cooldown_until = now + config.ACTION_COOLDOWN_MS
        if source=="static":
            self._static_need_gap = True
        else:
            self._need_gap = True
            self._hold_since = now
        # 到这里闸门都过了，动作**真的会执行** → 告诉推理线程"有人在用"，
        # 让它回到全速档。这就是空闲降频的判据（见 docs/MECHANISMS.md §2.2）。
        # ⚠ 判据刻意是"执行过动作"而不是"模型输出了高置信手势"：访客路过就会产生
        # 高分样本（实测走路有 15.5% 的采样 ≥0.8），用后者的话空闲计时永远被清零。
        self.it.mark_active()
        cn=self._page_name()
        # "已执行"提示：屏幕下方居中弹一下（src/ui/toast.py）。
        # 视频页的左/右实际是快退/快进，文案跟着改。
        label = CONTROL_CN.get(g, g)
        # 点赞就地做掉：文案里要带上"第几次"，所以执行与文案在这里一起算
        # （like_key 在上面算过，非空才走得到这里）
        if g=="like":
            label = self._count_like(like_key)
        if g in ("swipe_left","swipe_right") and (
                cn=="inheritor" or (cn=="detail" and self.pages["detail"].is_video_view())):
            label = "快退" if g=="swipe_left" else "快进"
        self._toast_text = "✔ 已执行：" + label
        self.toast.show_toast(self._toast_text)
        # ---- 全局动作：**不跟当前页面走**，任何页面上都生效 ----
        # 这两个只有静态手势（ok / 比耶）会产出，所以放在页面分发之前。
        if g=="home":
            self.stack.setCurrentIndex(IDX["home"])
            return
        if g=="guide":
            # 先切标签页再换页：设置页停在「参数调节」时，访客比个耶会看到一屏滑条，
            # 莫名其妙。先切好，页面出现时就已经是「手势说明」了（也不会看到跳一下）。
            self.pages["settings"].show_gestures()
            self.stack.setCurrentIndex(IDX["settings"])
            return
        if cn=="home":
            hp=self.pages["home"]
            # 单击 = 激活选中项：项目卡进详情页、传承人卡进传承人页那一位
            # （由首页自己按卡片类型分发，这里不关心它是哪一种）
            if g=="click": hp.activate_current()
            elif g=="swipe_left": hp._prev()      # 扁平顺序上一步（首尾环绕）
            elif g=="swipe_right": hp._next()
            elif g=="swipe_up": hp._up()          # 换到上一排
            elif g=="swipe_down": hp._down()      # 换到下一排
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
        # 提示胶囊要贴着底部居中，窗口尺寸一变就得重算
        self.toast.place()
    def closeEvent(self,e):
        self.it.stop(); self.cw.stop(); e.accept()
