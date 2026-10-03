"""防重复触发（MainWindow._ocg 与 _on_result）的回归测试

这是整套手势交互里调试最久、也最容易被改动带坏的一块。

**2026-10 起机制简化成两道，都很短，且都不依赖机器快慢：**

  ① 冷却   从**触发**时刻起算，`ACTION_COOLDOWN_MS` 内不再响应
  ② 间隙   触发条件必须**先不成立一次**，下一次才算数

② 是对 docs/MECHANISMS.md §1.5 那个坑（首页点进详情 → 残留手势被当成第二次操作
→ 被弹回首页）的精确防护：同一个手势一直被识别时，触发条件始终成立，
间隙永远不来，于是不会再触发。

⚠ **②必须看"触发用的那个量"**（平滑置信度 vs `CONFIDENCE_THRESHOLD`）。
2026-10 修掉的那个错配就是这里：原先"松手"看的是**即时**置信度 < 0.35 ——
两个不同的量、两个不同的门槛，于是手放下了模型仍可能报 0.4~0.6，
永远等不到间隙，一路走到 `MAX_HOLD_MS` 兜底（现场表现是"要等好久"）。

测法是直接调用真实方法，用一个桩对象充当 MainWindow 实例——
不构造任何窗口，因此不会拖起 WebEngine、摄像头和模型（除 torch 的导入外）。
_ocg / _on_result 只依赖：stack.currentIndex()、pages[...]、cw.set_confidence()、
toast.show_toast()、_go_detail()、it.mark_active()，以及 _lg/_gc/_need_gap/
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
        self._cooldown_until = 0.0       # 冷却截止（从触发时刻起算）
        self._need_gap = False           # 触发条件还没"断"过
        self._hold_since = 0.0           # 上次触发时刻，只给防死锁兜底用
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
        self._need_gap = False
        self._cooldown_until = 0.0
        for _ in range(max(1, config.CONSISTENCY_COUNT)):
            self.ocg(g)

    def gap(self, gesture="0", conf=0.10, raw_gesture="0", raw_conf=0.05):
        """模拟"触发条件断了一次"：喂一个**平滑**置信度低于门槛的结果。

        间隙就是靠这个时刻记录的（见 _on_result）。
        """
        self.on_result({"gesture": gesture, "confidence": conf,
                        "raw_gesture": raw_gesture, "raw_confidence": raw_conf})

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
                        "DISPLAY_SWITCH_CONFIDENCE",
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
    """冷却：**从触发时刻**起算，`ACTION_COOLDOWN_MS` 内不再响应"""

    def test_冷却期内不再响应(self):
        self.h.fire("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"])
        self.h.gap()                                    # 触发条件断过一次
        self.h.clock.advance(config.ACTION_COOLDOWN_MS - 100)
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "冷却期内不该再次触发")

    def test_冷却从触发时刻起算而不是从间隙起算(self):
        """⚠ 这条守着本次的改动。

        原先冷却从"松手"起算，于是每次操作都要多等"手放下的时间"（0.6~5 秒），
        1.5 秒的冷却体感成了 2~6.5 秒。现在改成从**触发**起算：
        间隙来得再晚，也不该把冷却的截止时间往后推。
        """
        self.h.fire("click")
        deadline = self.h._cooldown_until
        self.h.clock.advance(config.ACTION_COOLDOWN_MS - 100)
        self.h.gap()                                    # 间隙姗姗来迟
        self.assertEqual(self.h._cooldown_until, deadline,
                         "间隙不该影响冷却的截止时刻")
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), ["current_index"], "冷却还没满")
        self.h.clock.advance(200)
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"),
                         ["current_index", "current_index"], "冷却满了就该能再做一次")

    def test_间隙未到时一直不响应(self):
        """同一个手势一直被识别 → 触发条件始终成立 → 间隙不来 → 不重复触发。

        这里特意**推进到远超冷却时长**再试，证明挡人的不是冷却，而是间隙。
        """
        self.h.fire("swipe_right")
        self.h.clock.advance(config.MAX_HOLD_MS - 100)   # 冷却早就过了，但还没到兜底
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "触发条件没断过，不该重复触发")

    def test_超过MAX_HOLD_MS强制放行(self):
        """防死锁兜底：模型一直报同一个手势、门槛之上不下来时，
        不能让整个展台对任何手势都没反应（那种坏法不报错、看着一切正常）。"""
        self.assertGreater(config.MAX_HOLD_MS, config.ACTION_COOLDOWN_MS,
                           "前提：兜底时限要长于冷却，否则冷却还没满就被兜底放行了")
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
      t=600  手还停在单击姿势，模型仍读成单击，触发条件**始终成立** → 间隙不来
    根因是换页时清掉了防护——恰恰在防护最该保留的时刻撤掉了它。
    """

    def test_换页不清掉间隙状态(self):
        self.h.fire("click")
        self.assertTrue(self.h._need_gap, "触发后应要求一个间隙")
        self.h._on_page_changed(IDX["detail"])
        self.assertTrue(self.h._need_gap,
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

        # 之后每 0.6 秒都还有"单击"被识别出来（慢松手），且平滑置信度一直很高
        # —— 触发条件始终成立，间隙永远不来，所以只能靠它挡住。
        # 总时长特意压在 MAX_HOLD_MS 以内，否则会走到防死锁兜底那条路上。
        for _ in range(4):
            h.clock.advance(600)
            h.on_result({"gesture": "2", "confidence": 0.95,
                         "raw_gesture": "2", "raw_confidence": 0.95})

        self.assertNotIn("activate_selected", h.page_calls("detail"),
                         "详情页不该被残留的单击触发'确认'（那会弹回首页）")


class TestGap(_Base):
    """间隙：触发条件必须**先不成立一次**，下一次才算数"""

    def test_触发条件不成立即记上间隙(self):
        self.h.fire("swipe_right")
        self.assertTrue(self.h._need_gap, "刚触发完应当要求一个间隙")
        self.h.gap()
        self.assertFalse(self.h._need_gap, "触发条件不成立了，应当记上间隙")
        self.assertIsNone(self.h._lg, "间隙应当顺带重置去抖")
        self.assertEqual(self.h._gc, 0)

    def test_触发条件仍成立时不算间隙(self):
        self.h.fire("swipe_right")
        self.h.on_result({"gesture": "6", "confidence": 0.95,
                          "raw_gesture": "6", "raw_confidence": 0.95})
        self.assertTrue(self.h._need_gap, "触发条件还成立，不该算作间隙")

    def test_间隙看的是触发用的那个量(self):
        """⚠ 这条守着 2026-10 修掉的那个错配。

        触发看的是**平滑**置信度（≥ `CONFIDENCE_THRESHOLD`）；原先"松手"却看
        **即时**置信度 < 0.35 —— 两个不同的量、两个不同的门槛。后果是：
        手放下了模型仍可能对残留画面报 0.4~0.6 的即时值，于是永远等不到松手，
        一路走到 `MAX_HOLD_MS` 兜底。现场表现就是"要等好久才能做下一个动作"。
        """
        # 即时值很低，但平滑值仍高 → 触发条件仍成立 → 不算间隙
        self.h.fire("swipe_right")
        self.h.on_result({"gesture": "6", "confidence": 0.95,
                          "raw_gesture": "6", "raw_confidence": 0.10})
        self.assertTrue(self.h._need_gap,
                        "触发条件还成立（平滑值高），不该因为即时值低就算作间隙")

        # 反过来：即时值很高，但平滑值掉到门槛以下 → 触发条件不成立 → 算间隙
        self.h.on_result({"gesture": "6", "confidence": 0.20,
                          "raw_gesture": "6", "raw_confidence": 0.90})
        self.assertFalse(self.h._need_gap,
                         "触发条件已不成立（平滑值低），应当记上间隙")

    def test_门槛边界(self):
        """正好等于门槛算"成立"（触发那边用的是 `>=`），所以不算间隙"""
        self.h.fire("swipe_right")
        self.h.on_result({"gesture": "6", "confidence": config.CONFIDENCE_THRESHOLD,
                          "raw_gesture": "6", "raw_confidence": 0.5})
        self.assertTrue(self.h._need_gap, "恰好等于门槛仍算成立")


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
        """只有"真的执行了"才算。被冷却/间隙挡下的不是有效操作。"""
        self.h.fire("swipe_right")
        n = self.h.it.active_calls
        self.h.ocg("swipe_right")          # 触发条件没断过 → 被间隙挡住
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
    """屏幕下方胶囊提示的文案（视频页的左右要说成快退/快进）"""

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
