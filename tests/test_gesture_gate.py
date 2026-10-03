"""触发闸门（MainWindow._ocg 与 _on_result）的回归测试

这是整套手势交互里调试最久、也最容易被参数改动带坏的一块。

**2026-10 起机制简化了**：原先三道闸门（去抖 / 冷却 / 锁存），现在只剩**一道
「动作冷却」**，而且冷却**从"松手"起算，不是从"触发"起算**。理由见 _on_result 的注释：
从触发起算会把 §1.5 那个坑放回来（首页点进详情 → 被残留手势弹回首页）。
`MAX_HOLD_MS` 是**防死锁**的兜底（模型一直报同一手势、等不到松手时别让展台
彻底没反应），不是防误触发。

测法是直接调用真实方法，用一个桩对象充当 MainWindow 实例——
不构造任何窗口，因此不会拖起 WebEngine、摄像头和模型（除 torch 的导入外）。
_ocg / _on_result 只依赖：stack.currentIndex()、pages[...]、cw.set_confidence()、
toast.show_toast()、_go_detail()、it.mark_active()，以及 _lg/_gc/_pending_release/
_cooldown_until/_hold_since/_toast_text 这些状态字段
（改 MainWindow.__init__ 时要同步这里的桩）。
"""
import collections
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.ui.main_window import MainWindow, IDX


class _Clock:
    """可控时钟。替换 main_window 模块里的 time，让冷却的时长能被精确断言，
    而不是靠 sleep 去赌真实时间。"""

    def __init__(self):
        self.ms = 0.0

    def time(self):
        return self.ms / 1000.0

    def advance(self, ms):
        self.ms += ms


class _Calls:
    """记录被调用的假页面/假控件。构造时可指定某些"查询型"方法的返回值
    （例如 is_video_view()），其余方法一律记录调用并返回 None。"""

    def __init__(self, **returns):
        self.calls = []
        self._returns = returns

    def __getattr__(self, name):
        # 只挡 dunder，别挡 _next/_prev 这类单下划线的真实页面方法。
        # self.calls / self._returns 在 __init__ 里已进 __dict__，
        # 正常查找命中就不会走到 __getattr__，没有递归风险。
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        def f(*a, **kw):
            self.calls.append((name,) + a)
            return self._returns.get(name)

        return f

    def names(self):
        return [c[0] for c in self.calls]


class _FakeIt:
    """推理线程的桩。

    闸门放行动作时会调 `mark_active()` 通知它"有人在用"—— 那是空闲降频的判据
    （见 docs/MECHANISMS.md §2.2）。这条判据**失效方向是危险的**（漏调就一直降频、
    访客手势变迟钝，还不报错），所以桩必须能数出调用次数。
    """

    def __init__(self):
        self.active_calls = 0

    def mark_active(self):
        self.active_calls += 1


class _Harness:
    """_ocg / _on_result 的最小运行环境"""

    def __init__(self, page="home"):
        self.clock = _Clock()
        self.pages = collections.defaultdict(_Calls)
        self.cw = _Calls()
        # _on_page_changed 会把这两个全局按钮一起置顶
        self.bc = _Calls()
        self.bs = _Calls()
        self._page_idx = IDX[page]
        # ---- 闸门状态字段（必须与 MainWindow.__init__ 保持一致）----
        self._lg = None
        self._gc = 0
        self._pending_release = False    # 动作已执行、还在等访客松手
        self._cooldown_until = 0.0       # 松手之后冷却的截止时刻
        self._hold_since = 0.0           # 动作执行时刻，只给防死锁兜底用
        self._toast_text = ""
        # "已执行"提示的落点（src/ui/toast.py）。桩只要能记录调用即可
        self.toast = _Calls()
        # _on_result 的显示保持字段
        self._disp_label = None
        self._disp_conf = 0.0
        self._disp_ts = 0.0
        self.detail_arg = "unset"
        # 动作执行时要通知的推理线程桩（空闲降频判据）
        self.it = _FakeIt()

    @property
    def stack(self):
        return types.SimpleNamespace(currentIndex=lambda: self._page_idx)

    def _go_detail(self, i):
        self.detail_arg = i

    # 方法名必须和真身一致：_on_result 内部会回调 self._ocg(c)，
    # 桩上没有 _ocg 就会 AttributeError。ocg/on_result 只是好写的别名。
    def _ocg(self, g):
        MainWindow._ocg(self, g)

    def _on_result(self, r):
        MainWindow._on_result(self, r)

    def _on_page_changed(self, idx):
        self._page_idx = idx
        MainWindow._on_page_changed(self, idx)

    def ocg(self, g):
        self._ocg(g)

    def on_result(self, r):
        self._on_result(r)

    def fire(self, g):
        """清掉闸门状态后触发**一次**动作（用于只关心"分发到哪个页面方法"的用例）。

        喂的次数跟着 CONSISTENCY_COUNT 走（默认 1 = 一次即触发），
        这样这些用例不会因为去抖次数被现场调过而失真。
        """
        self._lg = None
        self._gc = 0
        self._pending_release = False
        self._cooldown_until = 0.0
        for _ in range(max(1, config.CONSISTENCY_COUNT)):
            self.ocg(g)

    def release(self, raw="0", raw_conf=0.05):
        """模拟"访客把手放下"：喂一个低于松手门槛的即时结果。

        冷却就是从这一刻起算的（见 _on_result）。
        """
        self.on_result({"gesture": "0", "confidence": 0.9,
                        "raw_gesture": raw, "raw_confidence": raw_conf})

    def page_calls(self, page):
        return self.pages[page].names()


class _Base(unittest.TestCase):
    """把闸门参数钉在**出厂值**上，避免用例结果依赖 config 当前被改成了什么

    注意是"跟随出厂值"而不是"写死某个数"：这样参数被改坏时用例会失败
    （写死就只能测出代码 bug，测不出配置 bug）。
    """

    def setUp(self):
        self._saved = {k: getattr(config, k) for k in
                       ("CONSISTENCY_COUNT", "ACTION_COOLDOWN_MS", "MAX_HOLD_MS",
                        "CONFIDENCE_THRESHOLD", "DISPLAY_CONFIDENCE",
                        "DISPLAY_SWITCH_CONFIDENCE", "RELEASE_CONFIDENCE",
                        "SEEK_STEP_MS", "TOAST_MS")}
        config.CONSISTENCY_COUNT = config.DEFAULTS["CONSISTENCY_COUNT"]
        config.ACTION_COOLDOWN_MS = config.DEFAULTS["ACTION_COOLDOWN_MS"]
        config.SEEK_STEP_MS = 30000
        import src.ui.main_window as mw
        self._mw = mw
        self._real_time = mw.time
        self.h = _Harness()
        mw.time = self.h.clock          # 装上可控时钟

    def tearDown(self):
        self._mw.time = self._real_time
        for k, v in self._saved.items():
            setattr(config, k, v)


class TestTriggerOnce(_Base):
    """去抖：默认 1 = 一次即触发；调大了才要求连续多次"""

    def test_默认一次即触发(self):
        """CONSISTENCY_COUNT 默认是 1，第一次识别就该触发。

        ⚠ 这条是 2026-10 改默认值时发现 bug 后加的：原先 _ocg 在"手势变了"那一支
        直接 `_lg=g; _gc=1; return`，于是**第一次永远轮不到触发** —— 那样把去抖
        次数设成 1 也是空转，设置页那根滑条形同虚设。这个用例守住它。
        """
        self.assertEqual(config.CONSISTENCY_COUNT, 1, "前提：出厂默认值是 1")
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "一次识别就该触发")

    def test_去抖次数可调(self):
        config.CONSISTENCY_COUNT = 4
        for _ in range(3):
            self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), [], "没攒够 4 次不该触发")
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), ["current_index"])

    def test_中途换手势要重新计数(self):
        config.CONSISTENCY_COUNT = 2
        self.h.ocg("swipe_right")
        self.h.ocg("swipe_left")
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), [], "穿插了别的手势，计数应重置")


class TestCooldown(_Base):
    """动作冷却 —— 现在**唯一**的防重复触发机制。

    它分两步：执行动作 → 等访客松手 → 松手后再静默 ACTION_COOLDOWN_MS。
    """

    def test_冷却期内不再响应(self):
        self.h.fire("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"])
        self.h.release()                                     # 松手 → 冷却起算
        self.h.clock.advance(config.ACTION_COOLDOWN_MS - 100)
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "冷却期内不该再次触发")

    def test_未松手前一直不响应(self):
        """原先由"锁存"挡的场景：动作执行了、手还举着 → 不该重复触发。

        这里特意**推进到远超冷却时长**再试，证明挡人的不是冷却，而是"还没松手"。
        """
        self.h.fire("swipe_right")
        self.h.clock.advance(config.ACTION_COOLDOWN_MS + 2000)
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "手还举着，不该重复触发")

    def test_未松手时换个动作也不响应(self):
        """等松手是**全局**的，不区分是哪个手势 —— 手没放下就不算"做完了"。"""
        self.h.fire("swipe_right")
        self.h.clock.advance(config.ACTION_COOLDOWN_MS + 2000)
        self.h.ocg("swipe_left")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "手还举着，换个手势也不该触发")

    def test_松手后冷却期满可以再做一次(self):
        self.h.fire("swipe_right")
        self.h.release()
        self.h.clock.advance(config.ACTION_COOLDOWN_MS + 100)
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next", "_next"])

    def test_冷却从松手起算而不是从触发起算(self):
        """⚠ §1.5 那个坑的核心。

        若从**触发**时刻起算，手还举着的访客在 1.5s 后就会被重复触发
        —— 首页点进详情 → 被弹回首页。
        """
        self.h.fire("click")
        self.h.clock.advance(config.ACTION_COOLDOWN_MS + 500)   # 若从触发起算，早就过了
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), ["current_index"], "还没松手，不该再触发")

        self.h.release()                                       # 现在才松手，冷却从这一刻起
        self.h.clock.advance(config.ACTION_COOLDOWN_MS - 100)
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), ["current_index"], "冷却还没满")
        self.h.clock.advance(200)
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"),
                         ["current_index", "current_index"], "冷却满了就该能再做一次")

    def test_超过MAX_HOLD_MS强制解锁(self):
        """防死锁兜底：模型一直报同一个手势、永远等不到"松手"时，
        不能让整个展台对任何手势都没反应（那种坏法不报错、看着一切正常）。"""
        self.assertGreater(config.MAX_HOLD_MS, config.ACTION_COOLDOWN_MS * 2,
                           "前提：兜底时限要明显长于冷却，否则正常慢松手也会被它打断")
        self.h.fire("swipe_right")
        self.h.clock.advance(config.MAX_HOLD_MS + 100)
        self.h.ocg("swipe_right")        # 这一下触发兜底，但它自己仍被刚起算的冷却挡住
        self.assertEqual(self.h.page_calls("home"), ["_next"])
        self.h.clock.advance(config.ACTION_COOLDOWN_MS + 100)
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next", "_next"],
                         "兜底生效之后应该能恢复响应")


class TestPageChangeKeepsGuard(_Base):
    """换页后残留手势不能在新页面上再触发一次

    实测踩过的完整场景（首页单击 → 慢松手 → 被弹回首页）：
      t=0    首页单击触发"确认" → 进入详情页
      t≈0    换页，去抖重置
      t=600  手还停在单击姿势，模型仍读成单击
      t≥1800 若此时"等松手"的防护已被换页清掉，就会再触发一次，
             而详情页的"确认"是激活选中项（默认"返回主页"）→ 弹回首页
    根因是换页时清掉了防护——恰恰在防护最该保留的时刻撤掉了它。
    """

    def test_换页不清掉等松手状态(self):
        self.h.fire("click")
        self.assertTrue(self.h._pending_release, "触发后应进入等松手状态")
        self.h._on_page_changed(IDX["detail"])
        self.assertTrue(self.h._pending_release,
                        "换页不该清它——用户的手还停在原姿势上")

    def test_换页会重置去抖(self):
        self.h.fire("click")
        self.h._on_page_changed(IDX["detail"])
        self.assertIsNone(self.h._lg)
        self.assertEqual(self.h._gc, 0)

    def test_慢松手不会在新页面上重复触发(self):
        h = self.h
        # t=0 首页单击 → 进入详情页
        h.pages["home"] = _Calls(current_index=0)
        h.fire("click")
        self.assertEqual(h.detail_arg, 0, "首页单击应进入详情页")

        # 换页（用户的手还停在单击姿势上）
        h.pages["detail"] = _Calls()
        h._on_page_changed(IDX["detail"])

        # 之后每 0.6 秒都还有"单击"被识别出来（慢松手），且置信度一直很高
        # —— 高置信度意味着"松手"那条路径不会生效，只能靠等松手状态挡住。
        # 总时长特意压在 MAX_HOLD_MS 以内，否则会走到防死锁兜底那条路上。
        for _ in range(5):
            h.clock.advance(600)
            h.on_result({"gesture": "2", "confidence": 0.95,
                         "raw_gesture": "2", "raw_confidence": 0.95})

        self.assertNotIn("activate_selected", h.page_calls("detail"),
                         "详情页不该被残留的单击触发'确认'（那会弹回首页）")


class TestRelease(_Base):
    """松手判定：即时置信度掉到 RELEASE_CONFIDENCE 以下 → 冷却开始计时"""

    def test_低置信度视为松手并起算冷却(self):
        self.h.fire("swipe_right")
        self.assertEqual(self.h._cooldown_until, 0.0, "触发的那一刻冷却还不该起算")
        self.h.release()
        self.assertFalse(self.h._pending_release, "低置信度应视为已松手")
        self.assertEqual(self.h._cooldown_until,
                         self.h.clock.ms + config.ACTION_COOLDOWN_MS,
                         "冷却应从松手这一刻起算")
        self.assertIsNone(self.h._lg)
        self.assertEqual(self.h._gc, 0)

    def test_高置信度不算松手(self):
        self.h.fire("swipe_right")
        self.h.on_result({"gesture": "6", "confidence": 0.99,
                          "raw_gesture": "6", "raw_confidence": 0.90})
        self.assertTrue(self.h._pending_release, "手还举着，不该算松手")
        self.assertEqual(self.h._cooldown_until, 0.0, "没松手就不该起算冷却")

    def test_松手用的是独立门槛而不是显示门槛(self):
        """即时置信度落在两个门槛**之间**时，不该判为松手。

        这两条线曾经共用一个常量（`DISPLAY_CONFIDENCE`）。2026-09 为了治悬浮窗
        乱闪把显示门槛抬到 0.6；如果"松手"还跟着它走，访客仍在做手势时就会
        提前松手 —— 那是**悄悄削弱防护**，而且不会报任何错。
        所以拆成了两条线，这条用例守住它们不再联动。
        """
        self.assertLess(config.RELEASE_CONFIDENCE, config.DISPLAY_CONFIDENCE,
                        "前提：松手门槛低于显示门槛，本用例才有区分度")
        self.h.fire("swipe_right")
        mid = (config.RELEASE_CONFIDENCE + config.DISPLAY_CONFIDENCE) / 2
        self.h.on_result({"gesture": "6", "confidence": 0.99,
                          "raw_gesture": "6", "raw_confidence": mid})
        self.assertTrue(self.h._pending_release,
                        "raw=%.2f 高于松手门槛(%.2f)，不该算松手 —— "
                        "算了就说明又在拿显示门槛当松手判据"
                        % (mid, config.RELEASE_CONFIDENCE))


class TestActiveNotification(_Base):
    """动作真的执行时，必须通知推理线程"有人在用" —— 那是空闲降频的判据。

    ⚠ 这条判据的**失效方向是危险的**：漏调的话系统会永远认为空闲 → 永远降频 →
    访客手势变迟钝（最多多等 1s），而且**不报任何错**。所以单独守住。
    （判据从"模型输出高置信手势"改成"执行了动作"，就是因为前者会被路人的
    高分样本反复清零 —— 见 docs/MECHANISMS.md §2.2。）
    """

    def test_动作执行时通知活跃(self):
        before = self.h.it.active_calls
        self.h.fire("swipe_right")
        self.assertEqual(self.h.it.active_calls, before + 1,
                         "动作执行了却没通知推理线程 → 空闲计时不被清零 → 会一直降频")

    def test_被闸门挡下时不算活跃(self):
        """只有"真的执行了"才算。被冷却/等松手挡下的不是有效操作。"""
        self.h.fire("swipe_right")
        n = self.h.it.active_calls
        self.h.ocg("swipe_right")          # 手还举着 → 被"等松手"挡住
        self.assertEqual(self.h.it.active_calls, n,
                         "被闸门挡下的动作不该算活跃（否则路人抖动也会被当成有人用）")

    def test_去抖未满时不算活跃(self):
        """第一次识别还不够触发，不该清空空闲计时"""
        config.CONSISTENCY_COUNT = 3
        self.h._lg = None
        self.h._gc = 0
        n = self.h.it.active_calls
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.it.active_calls, n, "去抖未满就通知活跃了")


class TestTriggerThreshold(_Base):
    """触发走平滑结果、且要过 CONFIDENCE_THRESHOLD"""

    def test_低于触发门槛不分发(self):
        self.h._page_idx = IDX["inheritor"]
        config.CONFIDENCE_THRESHOLD = 0.6
        for _ in range(4):
            self.h.on_result({"gesture": "5", "confidence": 0.5,
                              "raw_gesture": "5", "raw_confidence": 0.5})
        self.assertEqual(self.h.page_calls("inheritor"), [], "置信度不足不该触发")

    def test_达到门槛后分发(self):
        self.h._page_idx = IDX["inheritor"]
        config.CONFIDENCE_THRESHOLD = 0.6
        for _ in range(2):
            self.h.on_result({"gesture": "5", "confidence": 0.9,
                              "raw_gesture": "5", "raw_confidence": 0.9})
        self.assertEqual(self.h.page_calls("inheritor"), ["next_person"])

    def test_未绑定的类别不分发(self):
        self.h._page_idx = IDX["inheritor"]
        for _ in range(4):
            self.h.on_result({"gesture": "0", "confidence": 0.99,   # B0A 单指指向，无映射
                              "raw_gesture": "0", "raw_confidence": 0.99})
        self.assertEqual(self.h.page_calls("inheritor"), [])


class TestPageRouting(_Base):
    """_ocg 按当前页分发到哪个方法（对应设置页的手势对照表）"""

    def test_首页(self):
        h = self.h
        h.fire("swipe_left");  self.assertEqual(h.page_calls("home"), ["_prev"])
        h.fire("swipe_right"); self.assertEqual(h.page_calls("home"), ["_prev", "_next"])
        h.pages["home"] = _Calls(current_index=3)
        h.fire("click")
        self.assertEqual(h.detail_arg, 3, "首页单击应进入当前选中项的详情")

    def test_详情页主视图(self):
        # is_video_view() 每次会被调两次：一次用于生成提示文案、一次用于分发
        self.h._page_idx = IDX["detail"]
        self.h.fire("swipe_left");  self.assertEqual(self.h.page_calls("detail")[-1], "select_prev")
        self.h.fire("swipe_right"); self.assertEqual(self.h.page_calls("detail")[-1], "select_next")
        self.h.fire("click");       self.assertEqual(self.h.page_calls("detail")[-1],
                                                     "activate_selected")

    def test_详情页视频子页_左右变快退快进(self):
        h = self.h
        h._page_idx = IDX["detail"]
        h.pages["detail"] = _Calls(is_video_view=True)
        h.fire("swipe_left")
        self.assertEqual(h.page_calls("detail"), ["is_video_view", "is_video_view", "seek"])
        self.assertEqual(h.pages["detail"].calls[-1][1], -config.SEEK_STEP_MS)
        h.fire("swipe_right")
        self.assertEqual(h.pages["detail"].calls[-1][1], config.SEEK_STEP_MS)
        h.fire("click")
        self.assertEqual(h.page_calls("detail")[-1], "activate_selected")

    def test_传承人页(self):
        h = self.h
        h._page_idx = IDX["inheritor"]
        h.fire("swipe_down");  self.assertEqual(h.page_calls("inheritor"), ["next_person"])
        h.fire("swipe_up");    self.assertEqual(h.page_calls("inheritor"),
                                                ["next_person", "prev_person"])
        h.fire("swipe_left");  self.assertEqual(h.page_calls("inheritor")[-1], "seek_back")
        h.fire("swipe_right"); self.assertEqual(h.page_calls("inheritor")[-1], "seek_forward")
        h.fire("click");       self.assertEqual(h.page_calls("inheritor")[-1], "confirm")

    def test_3D页(self):
        h = self.h
        h._page_idx = IDX["viewer"]
        for g, m in (("zoom_in", "zoom_in"), ("zoom_out", "zoom_out"), ("circle", "circle")):
            h.fire(g)
            self.assertEqual(h.page_calls("viewer")[-1], m)
        h.fire("click")
        self.assertEqual(h.page_calls("viewer")[-1], "activate_selected")


class TestToast(_Base):
    """右上角"已执行"提示的文案（视频页的左右要说成快退/快进）"""

    def test_普通页面用控制名(self):
        self.h.fire("swipe_right")
        self.assertIn("向右", self.h._toast_text)

    def test_提示真的被推给了胶囊控件(self):
        """文案算对了还不够 —— 得真的送到屏幕上那个胶囊里。

        （2026-10 把提示从右上角小字搬到屏幕下方居中的 `ToastOverlay` 之后加的。）
        """
        self.h.fire("swipe_right")
        self.assertEqual(self.h.toast.calls, [("show_toast", self.h._toast_text)],
                         "动作执行了却没把提示交给胶囊控件")

    def test_传承人页左右说快进快退(self):
        self.h._page_idx = IDX["inheritor"]
        self.h.fire("swipe_left")
        self.assertIn("快退", self.h._toast_text)
        self.h.fire("swipe_right")
        self.assertIn("快进", self.h._toast_text)

    def test_详情页视频子页左右说快进快退(self):
        self.h._page_idx = IDX["detail"]
        self.h.pages["detail"] = _Calls(is_video_view=True)
        self.h.fire("swipe_left")
        self.assertIn("快退", self.h._toast_text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
