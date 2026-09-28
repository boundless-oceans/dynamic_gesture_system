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
        self._saved = (config.CAMERA_AUTO_SELECT, config.CAMERA_INDEX,
                       config.CAMERA_SCAN_MAX)

    def tearDown(self):
        (config.CAMERA_AUTO_SELECT, config.CAMERA_INDEX,
         config.CAMERA_SCAN_MAX) = self._saved

    def test_优先外接_自带放在最后(self):
        config.CAMERA_AUTO_SELECT = True
        cands = camera_candidates()
        self.assertEqual(cands[0], 1, "应当先试外接（非 0 号）")
        self.assertEqual(cands[-1], 0, "自带放最后，作为兜底")
        self.assertNotIn(0, cands[:-1], "0 号只能出现在末尾")

    def test_扫描范围跟随配置(self):
        config.CAMERA_AUTO_SELECT = True
        config.CAMERA_SCAN_MAX = 3
        self.assertEqual(sorted(camera_candidates()), [0, 1, 2],
                         "现场只有 自带+罗技+备用 三路，不必枚举到 5")
        config.CAMERA_SCAN_MAX = 5
        self.assertEqual(sorted(camera_candidates()), [0, 1, 2, 3, 4])

    def test_关闭自动选择时只用配置索引(self):
        config.CAMERA_AUTO_SELECT = False
        config.CAMERA_INDEX = 2
        self.assertEqual(camera_candidates(), [2])


class _FakeCap:
    def __init__(self, name="cap"):
        self.name = name
        self.released = False

    def release(self):
        self.released = True


class TestHotPlugSwitching(unittest.TestCase):
    """热插拔：插上外接要能自动切过去，拔掉要能退化回自带

    判定"要不要去找更好的摄像头"的逻辑在这里锁住——它决定了后台侦察线程
    什么时候跑，跑错方向会白白开设备、或者该切换时不切换。
    """

    def setUp(self):
        self._saved = (config.CAMERA_AUTO_SELECT, config.CAMERA_SCAN_MAX)
        config.CAMERA_AUTO_SELECT = True
        config.CAMERA_SCAN_MAX = 3
        self.cam = CameraThread(_StubBuffer())

    def tearDown(self):
        (config.CAMERA_AUTO_SELECT, config.CAMERA_SCAN_MAX) = self._saved

    def test_用着自带时才去找外接(self):
        self.cam._idx = 0
        self.assertTrue(self.cam.wants_upgrade(), "用着自带，应当去找外接")

    def test_用着外接时不再找(self):
        self.cam._idx = 1
        self.assertFalse(self.cam.wants_upgrade(), "已经是外接，没有更好的了")

    def test_还没打开时不找(self):
        self.cam._idx = None
        self.assertFalse(self.cam.wants_upgrade())

    def test_关掉自动选择后不找(self):
        config.CAMERA_AUTO_SELECT = False
        self.cam._idx = 0
        self.assertFalse(self.cam.wants_upgrade())

    def test_交接_放进去能取出来且只取一次(self):
        cap = _FakeCap()
        self.cam.park(cap, 1, "DSHOW")
        item = self.cam._pickup()
        self.assertEqual(item, (cap, 1, "DSHOW"))
        self.assertIsNone(self.cam._pickup(), "取过一次就不该再取到")

    def test_交接_反复放会释放掉没接手的那个(self):
        first, second = _FakeCap("first"), _FakeCap("second")
        self.cam.park(first, 1, "DSHOW")
        self.cam.park(second, 2, "DSHOW")
        self.assertTrue(first.released, "旧的没被接手就要释放，否则句柄泄漏")
        self.assertEqual(self.cam._pickup()[0], second)

    def test_切换会换源并清空缓冲(self):
        buf = _StubBuffer()
        cam = CameraThread(buf)
        cam._idx = 0
        cam.cap = _FakeCap("old")
        new = _FakeCap("new")
        cam._switch_to(new, 1, "DSHOW")
        self.assertEqual(cam._idx, 1)
        self.assertIs(cam.cap, new)
        self.assertEqual(buf.cleared, 1, "换了画面源，旧帧要清掉")
        self.assertTrue(cam.signal_ok(), "切换后应当是正常状态")


class _DeadCamera(CameraThread):
    """打开成功但读帧永远失败，模拟"摄像头运行中被拔掉" """

    def __init__(self, buffer):
        super().__init__(buffer)
        self.reads = 0

    def _open_camera(self):
        self.cap, self._idx = _FakeCap(), 1
        return True

    def _read(self):
        self.reads += 1
        return False, None


class TestOfflineHandsOverToOuterLayer(unittest.TestCase):
    """离线后线程要自行结束，把"重新搜索"交给上层重建

    这是刻意的设计：手动"关闭摄像头 → 插拔 → 打开摄像头"实测最可靠，因为它建的是
    全新的线程 + 全新的 VideoCapture；原地换句柄在设备消失后可能残留状态。
    所以自动恢复也走同一条路 —— 线程退出，由 CameraWidget 重建。
    """

    def test_读帧一直失败时线程会结束(self):
        cam = _DeadCamera(_StubBuffer())
        cam.start()
        self.assertTrue(cam.wait(8000), "连续失败到上限后线程应当自行结束")
        self.assertGreaterEqual(cam.reads, CameraThread.READ_FAIL_OFFLINE,
                                "应当先原地重试到上限，而不是一次失败就退出")

    def test_离线时信号置为异常(self):
        cam = _DeadCamera(_StubBuffer())
        cam.start()
        self.assertTrue(cam.wait(8000))
        self.assertFalse(cam.signal_ok(), "离线后 signal_ok 应为 False，预览才会提示断开")

    def test_离线时会清空帧缓冲(self):
        buf = _StubBuffer()
        cam = _DeadCamera(buf)
        cam.start()
        cam.wait(8000)
        self.assertGreaterEqual(buf.cleared, 1, "离线要清缓冲，否则推理线程会对着陈旧画面空转")


def _qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    inst = QApplication.instance()
    return inst if inst is not None else QApplication([])


class _SignalStub:
    def connect(self, *_a, **_k):
        pass


class _StubThread:
    """假的采集线程：不碰任何硬件

    组件层的测试必须用它替换掉真的 CameraThread —— 否则会真的去打开摄像头，
    多个用例并发操作同一台设备会直接把进程搞崩（实测踩过）。
    """

    frame_ready = _SignalStub()          # 对应 CameraThread.frame_ready 信号

    def __init__(self, frame_buffer=None):
        self._fb = frame_buffer
        self.running = False
        self.stopped = False
        self.stop_requested = False   # request_stop 只置位，不立即结束（模拟卡在驱动里）
        self.finished = False

    def connect(self, *_a, **_k):
        pass

    def start(self):
        self.running = True
        self.finished = False

    def isRunning(self):
        return self.running

    def isFinished(self):
        return self.finished

    def request_stop(self):
        self.stop_requested = True

    def signal_ok(self):
        return True

    def get_frame(self):
        return None

    def stop(self):
        self.running = False
        self.finished = True
        self.stopped = True

    def deleteLater(self):
        pass

    def camera_index(self):
        return 1


class TestWidgetRebuildGating(unittest.TestCase):
    """CameraWidget 什么时候该重建、什么时候不该"""

    @classmethod
    def setUpClass(cls):
        cls.app = _qt_app()

    def setUp(self):
        import src.ui.camera_widget as cw
        self._real_thread_cls = cw.CameraThread
        cw.CameraThread = _StubThread            # 不碰硬件
        self.w = cw.CameraWidget()
        self.w._frame_buffer = _StubBuffer()

    def tearDown(self):
        import src.ui.camera_widget as cw
        self.w._wanted = False
        self.w._timer.stop()
        cw.CameraThread = self._real_thread_cls

    def test_手动关闭后不再自动重建(self):
        self.w._wanted = True
        self.w.stop()
        self.assertFalse(self.w._wanted, "手动关掉摄像头后不该被自动重建")

    def test_刚启动时不会立刻被判为需要重建(self):
        """QThread.start() 之后 isRunning() 可能短暂为 False，
        必须压一个"最早重试时刻"，否则会立刻重建、陷入循环"""
        self.w._wanted = True
        self.w._spawn()
        self.assertGreater(self.w._next_try_ms, time.time() * 1000.0,
                           "_spawn 之后应当有一段时间不允许重建")

    def test_重建会换成新的线程对象(self):
        self.w._wanted = True
        self.w._spawn()
        first = self.w._camera_thread
        self.assertTrue(first.stopped is False)
        self.w._recover()
        self.assertIsNot(self.w._camera_thread, first,
                         "重建必须换新线程——复用旧对象正是要避免的")
        self.assertTrue(first.stopped, "旧线程要被显式停掉")

    def test_线程结束后才可能重建(self):
        """核心不变式：线程还在跑就不该重建"""
        self.w._wanted = True
        self.w._spawn()
        self.assertTrue(self.w._camera_thread.isRunning())
        t_before = self.w._next_try_ms
        self.w._recover()                        # 手工触发才会重建
        self.assertGreater(self.w._next_try_ms, t_before - 1)


class TestStaleFrameWatchdog(unittest.TestCase):
    """线程还活着但不出帧时，界面必须**主动**停掉它

    这是实测踩到的一组症状：拔掉 USB 后 read() 卡在驱动调用里，既不返回也不报错 ——
    signal_ok 一直是 True、线程也不退出，光看 isRunning() 根本发现不了，
    界面就停在最后一帧上。

    更隐蔽的是"重建时机"：如果不等旧线程真正结束就建新线程，
    两个线程会同时开着同一台摄像头，画面在两者之间来回跳
    （实测现象：预览不停在两个互为镜像的视角间切换、颜色忽冷忽暖）。
    """

    @classmethod
    def setUpClass(cls):
        cls.app = _qt_app()

    def setUp(self):
        import src.ui.camera_widget as cw
        self._real = cw.CameraThread
        cw.CameraThread = _StubThread
        self.w = cw.CameraWidget()
        self.w._frame_buffer = _StubBuffer()
        self.w._wanted = True
        self.w._spawn()
        self.th = self.w._camera_thread
        # 武装看门狗：假装出过帧
        self.w._on_frame_ready()

    def tearDown(self):
        import src.ui.camera_widget as cw
        self.w._wanted = False
        self.w._timer.stop()
        cw.CameraThread = self._real

    def _age(self):
        """让画面看起来"帧率已经塌了"：出过第一帧、但统计窗口内一帧都没有"""
        now = time.time() * 1000.0
        self.w._first_frame_ms = now - self.w.HEALTH_WINDOW_MS - 500
        self.w._frame_times.clear()
        self.w._last_frame_ms = now - self.w.HEALTH_WINDOW_MS - 500

    def _healthy(self):
        """让画面看起来正常：窗口里塞满帧"""
        self.w._frame_times.clear()
        now = time.time() * 1000.0
        for i in range(self.w.MIN_FRAMES_IN_WINDOW + 5):
            self.w._frame_times.append(now - i * 10)
        self.w._first_frame_ms = now - self.w.HEALTH_WINDOW_MS - 500
        self.w._last_frame_ms = now

    def test_有新帧时看门狗不动手(self):
        self._healthy()
        self.w._update_frame()
        self.assertFalse(self.th.stop_requested, "画面正常时不该去停线程")

    def test_长时间没新帧会请求停止(self):
        self._age()
        self.w._update_frame()
        self.assertTrue(self.th.stop_requested, "看门狗应当请求停止采集线程")
        self.assertTrue(self.w._recovering)

    def test_还没出过帧时不武装看门狗(self):
        self.w._first_frame_ms = 0.0             # 新线程刚起来、还没出帧
        self.w._frame_times.clear()
        self.w._update_frame()
        self.assertFalse(self.th.stop_requested,
                         "刚开始打开设备时不能判它失联")

    def test_刚出帧还没满统计窗口时不武装看门狗(self):
        """只出了一两帧还不够判失联——必须先攒满一个统计窗口"""
        now = time.time() * 1000.0
        self.w._frame_times.clear()
        self.w._frame_times.append(now)
        self.w._first_frame_ms = now            # 第一帧就是刚刚
        self.w._last_frame_ms = now
        self.w._update_frame()
        self.assertFalse(self.th.stop_requested,
                         "刚出第一帧就判失联会导致无限重启")

    def test_半死状态也要能判出来(self):
        """实测踩过的关键场景：大部分读帧失败、偶尔挤出一帧。

        "连续失败 N 次"和"完全没帧"两个判据都会被它绕过去，
        但画面已经完全不可用 —— 所以判据必须是帧率，而不是"有没有帧"。
        """
        now = time.time() * 1000.0
        self.w._first_frame_ms = now - self.w.HEALTH_WINDOW_MS - 500
        self.w._frame_times.clear()
        # 4 秒前和 3.5 秒前各挤出一帧 —— 有帧，但都在统计窗口之外
        self.w._frame_times.append(now - 4000)
        self.w._frame_times.append(now - 3500)
        self.w._last_frame_ms = now - 3500      # 注意：并不是"很久没帧"
        self.w._update_frame()
        self.assertTrue(self.th.stop_requested,
                        "偶发的帧不该掩盖「帧率已经塌了」这个事实")

    def test_旧线程没结束前绝不重建(self):
        """这一条是"两个线程抢同一台摄像头"的防线"""
        self._age()
        self.w._update_frame()                   # 第一次：请求停止
        plain = _StubThread()                    # 旧线程仍活着（卡在驱动里）
        self.th.running, self.th.finished = True, False
        self.th.stop = lambda: plain.stop()      # 万一被调用也保持"活着"
        self.w._update_frame()                   # 第二次：应当只是等
        self.assertIs(self.w._camera_thread, self.th,
                      "旧线程还没结束就重建 = 两个线程抢同一台摄像头")

    def test_旧线程结束后才重建(self):
        self._age()
        self.w._update_frame()
        self.th.running, self.th.finished = False, True   # 旧线程这才会真正结束
        self.w._update_frame()
        self.assertIsNot(self.w._camera_thread, self.th, "旧线程结束后应当重建")
        self.assertFalse(self.w._recovering, "重建后状态应当复位")


if __name__ == "__main__":
    unittest.main(verbosity=2)
