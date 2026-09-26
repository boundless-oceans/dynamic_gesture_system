"""摄像头线程的启动 / 关闭语义

这里锁住的是一个实测踩过的严重 bug：**窗口关不掉**。

根因是 run() 里 _running 置位太晚 ——

    def run(self):
        self.cap = self._open()      # 打开设备可能阻塞几十秒
        ...
        self._running = True         # ← 阻塞期间调用的 stop() 被这次赋值覆盖

于是 stop() 把 _running 置 False 后，线程醒来又把它置回 True：线程继续跑、
wait() 永远等不到。表现出来就是"点了关闭没反应"，同时日志还在刷重连。

不碰真实硬件：把 _open_camera / _loop 换成可控的桩。
"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.core.camera import CameraThread, camera_candidates


class _StubBuffer:
    def __init__(self):
        self.cleared = 0

    def push(self, frame):
        pass

    def clear(self):
        self.cleared += 1

    def get_latest(self, n):
        return []


class _SlowOpenCamera(CameraThread):
    """模拟"打开设备很慢"（MSMF 下实测外接摄像头要几十秒）"""

    def __init__(self, buffer, block_s=1.0, succeed=True):
        super().__init__(buffer)
        self.block_s = block_s
        self.succeed = succeed
        self.entered = threading.Event()
        self.running_seen_at_entry = None
        self.loop_entered = False

    def _open_camera(self):
        self.running_seen_at_entry = self._running
        self.entered.set()
        time.sleep(self.block_s)
        return self.succeed

    def _loop(self):
        self.loop_entered = True
        super()._loop()


class TestRunningFlagSetBeforeBlocking(unittest.TestCase):

    def test_进入阻塞前运行标志已置位(self):
        """这是关不掉那个 bug 的根因：标志必须早于任何阻塞操作"""
        cam = _SlowOpenCamera(_StubBuffer(), block_s=0.1)
        cam.start()
        self.assertTrue(cam.entered.wait(2.0), "桩没被调用")
        self.assertIs(cam.running_seen_at_entry, True,
                      "_running 必须在 _open_camera() 之前置位，"
                      "否则阻塞期间的 stop() 会被覆盖掉")
        cam.stop()

    def test_阻塞期间请求停止_线程不会进入采集循环(self):
        buf = _StubBuffer()
        cam = _SlowOpenCamera(buf, block_s=1.2, succeed=True)
        cam.start()
        self.assertTrue(cam.entered.wait(2.0))
        time.sleep(0.2)                      # 确认它确实卡在"打开设备"里
        t0 = time.time()
        cam.stop()
        dt = time.time() - t0
        self.assertFalse(cam.isRunning(), "线程应当已经退出")
        self.assertLess(dt, CameraThread.STOP_WAIT_MS + 0.5,
                        "stop() 不该等满上限——打开返回后线程就该立刻结束")
        self.assertFalse(cam.loop_entered and cam._running,
                         "被请求停止后不该再进入采集循环")

    def test_stop等待有上限(self):
        """打开设备阻塞超过上限时，stop() 也必须返回，否则窗口关不掉"""
        cam = _SlowOpenCamera(_StubBuffer(), block_s=CameraThread.STOP_WAIT_MS / 1000.0 + 2.0)
        cam.start()
        self.assertTrue(cam.entered.wait(2.0))
        t0 = time.time()
        cam.stop()
        dt = time.time() - t0
        self.assertLess(dt, CameraThread.STOP_WAIT_MS / 1000.0 + 1.5,
                        "stop() 必须在有上限的时间内返回")
        self.assertTrue(cam._abandoned, "等待超时后应标记为已弃用")
        cam.wait(6000)                       # 让阻塞的那次调用走完，收尾

    def test_打开失败也能正常结束(self):
        cam = _SlowOpenCamera(_StubBuffer(), block_s=0.1, succeed=False)
        cam.start()
        self.assertTrue(cam.entered.wait(2.0))
        self.assertTrue(cam.wait(3000), "打开失败时线程应当自行结束")
        self.assertFalse(cam.loop_entered)


class TestCameraCandidates(unittest.TestCase):

    def setUp(self):
        self._saved = (config.CAMERA_AUTO_SELECT, config.CAMERA_INDEX)

    def tearDown(self):
        config.CAMERA_AUTO_SELECT, config.CAMERA_INDEX = self._saved

    def test_优先外接_自带放在最后(self):
        config.CAMERA_AUTO_SELECT = True
        cands = camera_candidates()
        self.assertEqual(cands[0], 1, "应当先试外接（非 0 号）")
        self.assertEqual(cands[-1], 0, "自带放最后，作为兜底")
        self.assertEqual(sorted(cands), list(range(5)), "候选应当覆盖 0~4 且不重复")

    def test_关闭自动选择时只用配置索引(self):
        config.CAMERA_AUTO_SELECT = False
        config.CAMERA_INDEX = 2
        self.assertEqual(camera_candidates(), [2])


if __name__ == "__main__":
    unittest.main(verbosity=2)
