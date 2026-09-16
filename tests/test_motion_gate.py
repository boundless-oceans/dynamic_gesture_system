"""动静门控：画面没动作时跳过推理

这块一旦出错是"手势时好时坏"，很难在现场定位，所以判定逻辑要能被精确断言。
用可控时钟，不依赖真实等待。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.core.motion_gate import MotionGate


class _Clock:
    def __init__(self):
        self.ms = 1000.0

    def time(self):
        return self.ms / 1000.0

    def advance(self, ms):
        self.ms += ms


def _frame(v=128, shape=(480, 640, 3)):
    return np.full(shape, v, dtype=np.uint8)


def _frame_with_patch(size=100, base=128, patch=255, shape=(480, 640, 3)):
    """在纯色帧中央挖一块 size×size 的高对比方块，模拟"画面里出现了一只移动的手。

    注意 box 语义是 (y0, y1, x0, x1)，写反会得到空切片、造不出任何变化。
    """
    f = _frame(base, shape)
    h, w = shape[:2]
    y0, x0 = (h - size) // 2, (w - size) // 2
    f[y0:y0 + size, x0:x0 + size] = patch
    return f


class TestMotionGate(unittest.TestCase):

    def setUp(self):
        self.clock = _Clock()
        self.g = MotionGate(enabled=True, grace_ms=2000, threshold=0.002,
                            time_fn=self.clock.time)

    def test_首帧视为有动作(self):
        """没有参照帧时不能判成静止，否则启动瞬间会被挡住"""
        self.assertTrue(self.g.active(), "初始就该是可推理状态")
        self.g.feed(_frame())
        self.assertTrue(self.g.active())

    def test_画面不变时进入静止(self):
        self.g.feed(_frame())
        self.clock.advance(2100)                 # 超过宽限期
        self.assertFalse(self.g.active(), "画面一直没变，应判为静止")
        self.g.feed(_frame())                    # 再来一帧同样的
        self.assertFalse(self.g.active())

    def test_画面变化时保持活跃(self):
        self.g.feed(_frame())
        self.clock.advance(2100)
        self.assertFalse(self.g.active())
        self.g.feed(_frame_with_patch(size=100))     # 出现一块变化区域
        self.assertTrue(self.g.active(), "有变化就该恢复活跃")

    def test_宽限期内持续活跃(self):
        """宽限期是为了让"松手解锁"仍能生效：动作停了也要继续推理一会儿"""
        self.g.feed(_frame())
        self.g.feed(_frame_with_patch())
        self.clock.advance(1999)                 # 仍在 2000ms 宽限期内
        self.assertTrue(self.g.active())
        self.clock.advance(2)                    # 越过宽限期
        self.assertFalse(self.g.active())

    def test_小幅噪声不算动作(self):
        """传感器噪声不该把门控一直撑开"""
        g = MotionGate(enabled=True, grace_ms=2000, threshold=0.002,
                       time_fn=self.clock.time)
        rng = np.random.default_rng(0)
        g.feed(_frame(128))
        for _ in range(30):
            noisy = _frame(128)
            noisy = np.clip(noisy.astype(int) + rng.integers(-3, 4, noisy.shape), 0, 255
                            ).astype(np.uint8)
            g.feed(noisy)
        self.clock.advance(2100)
        self.assertFalse(g.active(), "±3 灰度噪声不该被判成动作")

    def test_手掌量级的变化能触发(self):
        """灵敏度偏向"宁可过灵"：正常幅度的手势绝不能被挡掉"""
        self.g.feed(_frame())
        self.clock.advance(2100)
        self.assertFalse(self.g.active())
        self.g.feed(_frame_with_patch(size=60))      # 640x480 里的 60x60
        self.assertTrue(self.g.active())

    def test_门控能看见的最小变化量级(self):
        """记录门控的粒度下限，避免以后有人误以为"任何细微变化都会唤醒"。

        阈值作用在 80x60 的分析图上（0.002 = 约 10 个像素），
        经 8 倍降采样 + 高斯模糊后，比"原图里几十像素见方"更小的变化会被忽略。
        这是刻意的：摄像头噪声的实测最大值就在这个量级附近，
        阈值再低门控会被噪声一直撑开、一点算力也省不下来。
        正常距离的手在画面里远大于这个尺寸，不受影响。
        """
        self.g.feed(_frame())
        self.clock.advance(2100)
        self.assertFalse(self.g.active())
        self.g.feed(_frame_with_patch(size=8))       # 8x8：远低于下限
        self.assertFalse(self.g.active(), "极小的变化应被忽略")

        self.g.feed(_frame(128))                     # 恢复静止
        self.clock.advance(2100)
        self.g.feed(_frame_with_patch(size=60))      # 60x60：明显高于下限
        self.assertTrue(self.g.active(), "60x60 的变化必须能唤醒")

    def test_关闭时恒为活跃(self):
        g = MotionGate(enabled=False, time_fn=self.clock.time)
        g.feed(_frame())
        self.clock.advance(10 ** 6)
        self.assertTrue(g.active(), "门控关闭时不应阻挡推理")

    def test_关闭时不消耗算力(self):
        g = MotionGate(enabled=False, time_fn=self.clock.time)
        g.feed(_frame())
        self.assertEqual(g.frames_seen, 0, "关闭时应直接返回，不做任何计算")

    def test_异常帧不影响采集(self):
        """喂进来的帧有问题也不能抛出去——那会拖垮摄像头线程"""
        try:
            self.g.feed(np.zeros((0, 0, 3), dtype=np.uint8))
            self.g.feed(None)
        except Exception as e:                    # noqa: BLE001
            self.fail(f"feed() 不该抛异常: {e}")

    def test_reset_丢弃参照帧(self):
        self.g.feed(_frame())
        self.g.feed(_frame_with_patch())
        self.clock.advance(2100)
        self.assertFalse(self.g.active())
        self.g.reset()                            # 相当于摄像头重启
        self.assertTrue(self.g.active(), "reset 后应按首帧处理，视为活跃")
        self.assertEqual(self.g.frames_seen, 0)

    def test_灵敏度可调(self):
        loose = MotionGate(enabled=True, grace_ms=2000, threshold=0.5,
                           time_fn=self.clock.time)     # 要求半个画面变化
        loose.feed(_frame())
        loose.feed(_frame_with_patch())
        self.clock.advance(2100)
        self.assertFalse(loose.active(), "阈值很高时小块变化不该算动作")


class TestConfigWiring(unittest.TestCase):

    def test_配置项存在且被门控接受(self):
        from src import config
        g = MotionGate(enabled=config.MOTION_GATE_ENABLED,
                       grace_ms=config.MOTION_GATE_GRACE_MS,
                       threshold=config.MOTION_THRESHOLD)
        self.assertEqual(g.threshold, config.MOTION_THRESHOLD)
        self.assertEqual(g.grace_ms, config.MOTION_GATE_GRACE_MS)

    def test_门控参数出现在设置页可调项(self):
        from src import config
        keys = [s["key"] for s in config.TUNABLE]
        self.assertIn("MOTION_THRESHOLD", keys)
        self.assertIn("MOTION_GATE_GRACE_MS", keys)


if __name__ == "__main__":
    unittest.main(verbosity=2)
