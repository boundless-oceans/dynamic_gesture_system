"""空闲降频阶梯：长时间识别不到手势时逐档降低推理频率

判据是"模型自己的输出"（raw 置信度 >= CONFIDENCE_THRESHOLD），不依赖画面差分，
所以不受现场光线与摄像头噪声影响。这里只测阶梯逻辑本身——不启动线程，
直接构造 InferenceThread 并摆布它的空闲计时。
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.core.inference import InferenceThread


class _StubRecognizer:
    """只提供 InferenceThread 需要的那点接口"""

    def __init__(self):
        self.reset_count = 0

    def reset_smoothing(self):
        self.reset_count += 1


class _LadderTestBase(unittest.TestCase):

    # 子类设 True 表示"要测**出厂值**"，此时不套用下面的夹具阶梯。
    # TestLadderConfig 必须用出厂值 —— 否则它测的是一份写死的副本，
    # 改了 config.IDLE_LADDER 也没人发现（这个坑实际踩过）。
    USE_SHIPPED_LADDER = False

    def setUp(self):
        self._saved = {
            "IDLE_LADDER": list(getattr(config, "IDLE_LADDER", [])),
            "IDLE_LADDER_ENABLED": getattr(config, "IDLE_LADDER_ENABLED", True),
        }
        if not self.USE_SHIPPED_LADDER:
            config.IDLE_LADDER = [(0, 20), (10000, 300), (60000, 1000)]
        config.IDLE_LADDER_ENABLED = True
        # 不启动线程：QThread 对象可以直接构造，只是不 start()
        self.it = InferenceThread(None, _StubRecognizer())

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(config, k, v)

    def _idle(self, ms):
        """把"上次活跃"推到 ms 毫秒之前"""
        self.it._last_active_ms = time.time() * 1000.0 - ms


class TestLadderSteps(_LadderTestBase):

    def test_刚活跃时是全速档(self):
        self.assertEqual(self.it.ladder_step(), 0)
        self.assertEqual(self.it.interval_ms(0), 20)

    def test_空闲不足10秒仍是全速(self):
        """这一条直接对应"访客中途停几秒"的场景——绝不能降频。

        **不测贴着阈值的 9999ms**：Windows 上 `time.time()` 的粒度约 15ms，
        差 1ms 的边界会随机翻车（实际踩到过一条 `0 != 1`）。
        "刚好到阈值就降频"由 `_idle(10000)` 那条覆盖。
        """
        for pause_ms in (2000, 3000, 5000, 9000):
            with self.subTest(pause_ms=pause_ms):
                self._idle(pause_ms)
                self.assertEqual(self.it.ladder_step(), 0,
                                 f"停顿 {pause_ms}ms 不该离开全速档")

    def test_空闲10秒进第二档(self):
        self._idle(10000)
        self.assertEqual(self.it.ladder_step(), 1)
        self.assertEqual(self.it.interval_ms(1), 300)

    def test_空闲60秒进最深档(self):
        self._idle(60000)
        self.assertEqual(self.it.ladder_step(), 2)
        self.assertEqual(self.it.interval_ms(2), 1000)

    def test_档位边界(self):
        """只测"刚好到阈值"这一侧。

        "差一点没到"那一侧（7999 这种）不测：Windows 上 `time.time()` 粒度约 15ms，
        贴着阈值的断言会随机翻车。反正那条语义已经被
        `test_空闲不足10秒仍是全速` 用留足余量的值覆盖了。
        """
        self._idle(10000); self.assertEqual(self.it.ladder_step(), 1)
        self._idle(59999); self.assertEqual(self.it.ladder_step(), 1)
        self._idle(60000); self.assertEqual(self.it.ladder_step(), 2)

    def test_活跃后立刻回到全速(self):
        self._idle(120000)
        self.assertEqual(self.it.ladder_step(), 2)
        self.it.mark_active()
        self.assertEqual(self.it.ladder_step(), 0, "一旦识别到手势就该立刻回全速")

    def test_关掉开关后恒为全速(self):
        config.IDLE_LADDER_ENABLED = False
        self._idle(10 ** 7)
        self.assertEqual(self.it.ladder_step(), 0)
        self.assertEqual(self.it.interval_ms(0), config.IDLE_LADDER[0][1])

    def test_空阶梯不会崩(self):
        config.IDLE_LADDER = []
        self._idle(10 ** 7)
        self.assertEqual(self.it.ladder_step(), 0)
        self.assertEqual(self.it.interval_ms(0), config.INFERENCE_INTERVAL_MS)

    def test_越界的档位不会抛异常(self):
        self.assertEqual(self.it.interval_ms(99), config.IDLE_LADDER[-1][1])


class TestLadderConfig(_LadderTestBase):
    """这些是**出厂值**的体检 —— 必须测真的那份，不是夹具里的副本。"""

    USE_SHIPPED_LADDER = True

    def test_阶梯按空闲时长升序排列(self):
        """顺序错了会让档位选择出错（实现是"取最后一个满足的"）"""
        thresholds = [t for t, _ in config.IDLE_LADDER]
        self.assertEqual(thresholds, sorted(thresholds), "阈值必须升序")

    def test_第一档必须是零延迟全速(self):
        self.assertEqual(config.IDLE_LADDER[0][0], 0, "第一档的阈值必须是 0")
        self.assertLessEqual(config.IDLE_LADDER[0][1], 50,
                             "第一档应当是接近满速的间隔")

    def test_间隔随时长单调变长(self):
        intervals = [iv for _, iv in config.IDLE_LADDER]
        self.assertEqual(intervals, sorted(intervals), "越空闲间隔应越长")

    def test_最深档不超过1秒(self):
        """更深会让"访客走过来做的第一个手势"大概率被漏掉。

        空闲间隔 1s 时，一个 1 秒长的手势必然被覆盖；到 5s 只剩约 20% 命中率。
        """
        deepest = config.IDLE_LADDER[-1][1]
        self.assertLessEqual(deepest, 1000,
                             f"最深档 {deepest}ms 过深，会漏掉访客的第一个手势")

    def test_首次停顿阈值不小于5秒(self):
        """交互中"停几秒想一下"很常见，第一档阈值太小会频繁降频"""
        first_jump = config.IDLE_LADDER[1][0]
        self.assertGreaterEqual(first_jump, 5000,
                                f"第一档阈值 {first_jump}ms 太短，正常停顿就会降频")

    def test_活跃判据不再看置信度(self):
        """结构性守卫：`_last_active_ms` 只允许在 `__init__` 与 `mark_active` 里赋值。

        **判据曾经是「raw 置信度 ≥ CONFIDENCE_THRESHOLD 就算活跃」**，但实测
        **访客在镜头前走过（不做任何手势）也有 15.5% 的采样 ≥0.8** ——
        路人一走就把空闲计时清零，降频在「有人走动但没人互动」的博物馆常态下
        形同虚设。

        现在判据是「**真的执行过动作**」：main_window 在闸门放行后调
        `mark_active()`（正面行为由 tests/test_gesture_gate.py 的
        TestActiveNotification 覆盖）。推理线程内部**不该**再按置信度刷新它 ——
        多出来一次赋值，很可能就是有人把旧判据加了回来。
        """
        import inspect
        from src.core import inference as inf
        code = "\n".join(line for line in inspect.getsource(inf.InferenceThread).splitlines()
                         if not line.lstrip().startswith("#"))
        n = code.count("_last_active_ms =")
        self.assertEqual(
            n, 2,
            f"`_last_active_ms` 被赋值 {n} 次，应为 2 次（__init__ 与 mark_active）。"
            "多出来那次很可能是旧判据又回来了 —— 那会让路人走过就把空闲计时清零。")


if __name__ == "__main__":
    unittest.main(verbosity=2)
