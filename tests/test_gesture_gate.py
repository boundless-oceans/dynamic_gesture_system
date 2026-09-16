"""去抖 / 锁存 / 冷却状态机（MainWindow._ocg 与 _on_result）的回归测试

这是整套手势交互里调试最久、也最容易被参数改动带坏的一块：
CONSISTENCY_COUNT / ACTION_COOLDOWN_MS / MAX_LOCK_MS 任何一个调整，
"会不会误触发""会不会重复触发""松手后能不能再做一次"都会变。

测法是直接调用真实方法，用一个桩对象充当 MainWindow 实例——
不构造任何窗口，因此不会拖起 WebEngine、摄像头和模型（除 torch 的导入外）。
_ocg 只依赖这些成员：stack.currentIndex()、pages[...]、cw.set_custom()、
_go_detail()，以及 _lg/_gc/_locks/_cooldown_until/_toast_until 几个状态字段。
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
    """可控时钟。替换 main_window 模块里的 time，让冷却/锁存的时长能被精确断言，
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


class _Harness:
    """_ocg / _on_result 的最小运行环境"""

    def __init__(self, page="home"):
        self.clock = _Clock()
        self.pages = collections.defaultdict(_Calls)
        self.cw = _Calls()
        self._page_idx = IDX[page]
        # _ocg 的状态字段
        self._lg = None
        self._gc = 0
        self._locks = {}
        self._cooldown_until = 0.0
        self._toast_until = 0.0
        self._toast_text = ""
        # _on_result 的显示保持字段
        self._disp_label = None
        self._disp_conf = 0.0
        self._disp_ts = 0.0
        self.detail_arg = "unset"

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

    def ocg(self, g):
        self._ocg(g)

    def on_result(self, r):
        self._on_result(r)

    def fire(self, g):
        """清空冷却与锁存后触发一次动作（用于只关心"分发到哪个页面方法"的用例）"""
        self._locks.clear()
        self._cooldown_until = 0.0
        self._lg = None
        self._gc = 0
        self.ocg(g)
        self.ocg(g)

    def page_calls(self, page):
        return self.pages[page].names()


class _Base(unittest.TestCase):
    """固定去抖/冷却/锁存参数，避免用例结果依赖 config 当前值"""

    def setUp(self):
        self._saved = {k: getattr(config, k) for k in
                       ("CONSISTENCY_COUNT", "ACTION_COOLDOWN_MS", "MAX_LOCK_MS",
                        "CONFIDENCE_THRESHOLD", "DISPLAY_CONFIDENCE",
                        "SEEK_STEP_MS", "TOAST_MS")}
        config.CONSISTENCY_COUNT = 2
        config.ACTION_COOLDOWN_MS = 900
        config.MAX_LOCK_MS = 2000
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


class TestDebounce(_Base):

    def test_需要连续N次才触发(self):
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), [], "第 1 次不该触发")
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "第 2 次应触发")

    def test_中途换手势要重新计数(self):
        self.h.ocg("swipe_right")
        self.h.ocg("swipe_left")
        self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), [], "穿插了别的手势，计数应重置")

    def test_去抖次数可调(self):
        config.CONSISTENCY_COUNT = 4
        for _ in range(3):
            self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), [])
        self.h.ocg("click")
        self.assertEqual(self.h.page_calls("home"), ["current_index"])


class TestCooldownAndLock(_Base):

    def test_冷却期内不再响应(self):
        self.h.fire("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"])
        self.h.clock.advance(500)                  # < ACTION_COOLDOWN_MS
        self.h._lg = None; self.h._gc = 0
        self.h.ocg("swipe_right"); self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "冷却期内不该再次触发")

    def test_锁存期内同一动作只触发一次(self):
        self.h.fire("swipe_right")
        self.h.clock.advance(1500)                 # 冷却已过，但 < MAX_LOCK_MS
        self.h._lg = None; self.h._gc = 0
        self.h.ocg("swipe_right"); self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next"], "未松手前不该重复触发")

    def test_锁存超时后可以再做一次(self):
        self.h.fire("swipe_right")
        self.h.clock.advance(2500)                 # > MAX_LOCK_MS，视为自动解锁
        self.h._lg = None; self.h._gc = 0
        self.h.ocg("swipe_right"); self.h.ocg("swipe_right")
        self.assertEqual(self.h.page_calls("home"), ["_next", "_next"])

    def test_不同动作互不锁存(self):
        self.h.fire("swipe_right")
        self.h.clock.advance(1000)                 # 冷却已过，仍在 swipe_right 的锁存期
        self.h._lg = None; self.h._gc = 0
        self.h.ocg("swipe_left"); self.h.ocg("swipe_left")
        self.assertEqual(self.h.page_calls("home"), ["_next", "_prev"])


class TestLatchRelease(_Base):
    """松手解锁：即时置信度掉到显示门槛以下 → 清锁，要求重新做手势"""

    def test_低置信度清空锁存与去抖(self):
        self.h.fire("swipe_right")
        self.assertTrue(self.h._locks, "触发后应有锁存")
        self.h.on_result({"gesture": "6", "confidence": 0.99,
                          "raw_gesture": "0", "raw_confidence": 0.10})
        self.assertEqual(self.h._locks, {}, "低置信度应清锁")
        self.assertIsNone(self.h._lg)
        self.assertEqual(self.h._gc, 0)

    def test_高置信度不清锁(self):
        self.h.fire("swipe_right")
        locks = dict(self.h._locks)
        self.h.on_result({"gesture": "6", "confidence": 0.99,
                          "raw_gesture": "6", "raw_confidence": 0.90})
        self.assertEqual(self.h._locks, locks, "高置信度不应清锁")


class TestTriggerThreshold(_Base):
    """触发走平滑结果、且要过 CONFIDENCE_THRESHOLD"""

    def test_低于触发门槛不分发(self):
        self.h._page_idx = IDX["map"]
        config.CONFIDENCE_THRESHOLD = 0.6
        for _ in range(4):
            self.h.on_result({"gesture": "5", "confidence": 0.5,
                              "raw_gesture": "5", "raw_confidence": 0.5})
        self.assertEqual(self.h.page_calls("map"), [], "置信度不足不该触发")

    def test_达到门槛后分发(self):
        self.h._page_idx = IDX["map"]
        config.CONFIDENCE_THRESHOLD = 0.6
        for _ in range(2):
            self.h.on_result({"gesture": "5", "confidence": 0.9,
                              "raw_gesture": "5", "raw_confidence": 0.9})
        self.assertEqual(self.h.page_calls("map"), ["pan_down"])

    def test_未绑定的类别不分发(self):
        self.h._page_idx = IDX["map"]
        for _ in range(4):
            self.h.on_result({"gesture": "0", "confidence": 0.99,   # B0A 单指指向，无映射
                              "raw_gesture": "0", "raw_confidence": 0.99})
        self.assertEqual(self.h.page_calls("map"), [])


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

    def test_地图页(self):
        h = self.h
        h._page_idx = IDX["map"]
        for g, m in (("swipe_up", "pan_up"), ("swipe_down", "pan_down"),
                     ("swipe_left", "pan_left"), ("swipe_right", "pan_right"),
                     ("zoom_in", "zoom_in"), ("zoom_out", "zoom_out")):
            h.fire(g)
            self.assertEqual(h.page_calls("map")[-1], m, f"{g} 应路由到 {m}")

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
