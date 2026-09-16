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

    def setUp(self):
        self._saved = {
            "IDLE_LADDER": list(getattr(config, "IDLE_LADDER", [])),
            "IDLE_LADDER_ENABLED": getattr(config, "IDLE_LADDER_ENABLED", True),
        }
        config.IDLE_LADDER = [(0, 20), (8000, 300), (60000, 1000)]
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

    def test_空闲不足8秒仍是全速(self):
        """这一条直接对应"访客中途停 2~3 秒"的场景——绝不能降频"""
        for pause_ms in (2000, 3000, 5000, 7999):
            with self.subTest(pause_ms=pause_ms):
                self._idle(pause_ms)
                self.assertEqual(self.it.ladder_step(), 0,
                                 f"停顿 {pause_ms}ms 不该离开全速档")

    def test_空闲8秒进第二档(self):
        self._idle(8000)
        self.assertEqual(self.it.ladder_step(), 1)
        self.assertEqual(self.it.interval_ms(1), 300)

    def test_空闲60秒进最深档(self):
        self._idle(60000)
        self.assertEqual(self.it.ladder_step(), 2)
        self.assertEqual(self.it.interval_ms(2), 1000)

    def test_档位边界(self):
        self._idle(7999);  self.assertEqual(self.it.ladder_step(), 0)
        self._idle(8000);  self.assertEqual(self.it.ladder_step(), 1)
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

    def test_判据用的是触发门槛而非显示门槛(self):
        """实测：空场景 raw 置信度最大 0.491。

        若拿 DISPLAY_CONFIDENCE(0.35) 当判据，空场景有 4%~52% 的采样会被
        误认成"有手势"，空闲计时永远清零、降频永远不触发。
        """
        self.assertGreaterEqual(config.CONFIDENCE_THRESHOLD, 0.5,
                                "降频判据必须用一个空场景达不到的门槛")
        self.assertGreater(config.CONFIDENCE_THRESHOLD, config.DISPLAY_CONFIDENCE)


if __name__ == "__main__":
    unittest.main(verbosity=2)
