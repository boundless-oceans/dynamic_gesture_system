"""帧缓冲队列：摄像头线程写入、推理线程读取的交接点"""
import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from src.core.frame_buffer import FrameBuffer


def _frame(v, shape=(48, 64, 3)):
    return np.full(shape, v, dtype=np.uint8)


class TestFrameBuffer(unittest.TestCase):

    def test_初始为空(self):
        buf = FrameBuffer(maxlen=5)
        self.assertEqual(buf.size, 0)
        self.assertEqual(buf.get_latest(3), [])

    def test_攒不满窗口返回空(self):
        """推理线程靠这个判断"还没攒够帧"，返回空列表而不是短列表"""
        buf = FrameBuffer(maxlen=5)
        for i in range(3):
            buf.push(_frame(i))
        self.assertEqual(buf.size, 3)
        self.assertEqual(len(buf.get_latest(3)), 3)
        self.assertEqual(buf.get_latest(4), [], "不足 4 帧必须返回空列表")

    def test_溢出丢弃最旧帧(self):
        buf = FrameBuffer(maxlen=3)
        for i in range(5):
            buf.push(_frame(i))
        self.assertEqual(buf.size, 3)
        frames = buf.get_latest(3)
        self.assertEqual([int(f[0, 0, 0]) for f in frames], [2, 3, 4], "应保留最新的 3 帧")

    def test_push_会拷贝帧(self):
        """push 必须拷贝：否则调用方复用同一块内存时，缓冲里的历史帧会被改掉"""
        buf = FrameBuffer(maxlen=3)
        arr = _frame(7)
        buf.push(arr)
        arr[:] = 0
        self.assertEqual(int(buf.get_latest(1)[0][0, 0, 0]), 7, "缓冲内的帧不应被外部修改影响")

    def test_get_latest_返回拷贝(self):
        """取出的列表是快照，之后 push 不应改变已取出的结果"""
        buf = FrameBuffer(maxlen=5)
        buf.push(_frame(1))
        got = buf.get_latest(1)
        buf.push(_frame(2))
        self.assertEqual(len(got), 1)
        self.assertEqual(int(got[0][0, 0, 0]), 1)

    def test_clear(self):
        buf = FrameBuffer(maxlen=5)
        for i in range(3):
            buf.push(_frame(i))
        buf.clear()
        self.assertEqual(buf.size, 0)
        self.assertEqual(buf.get_latest(1), [])

    def test_线程安全(self):
        buf = FrameBuffer(maxlen=100)
        errors = []
        stop = threading.Event()

        def writer():
            for i in range(300):
                try:
                    buf.push(_frame(i % 256))
                except Exception as e:       # noqa: BLE001
                    errors.append(f"writer: {e}")
            stop.set()

        def reader():
            while not stop.is_set():
                try:
                    for f in buf.get_latest(4):
                        if f.shape != (48, 64, 3):
                            errors.append("shape mismatch")
                except Exception as e:       # noqa: BLE001
                    errors.append(f"reader: {e}")
                time.sleep(0.0005)

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)
        self.assertEqual(errors, [], f"并发读写报错: {errors[:5]}")
        self.assertEqual(buf.size, 100, "maxlen 应生效，不会无限增长")


if __name__ == "__main__":
    unittest.main(verbosity=2)
