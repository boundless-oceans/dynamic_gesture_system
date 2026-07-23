"""测试 F2a: 帧缓冲队列"""

import numpy as np
from src.core.frame_buffer import FrameBuffer


def test_basic():
    buf = FrameBuffer(maxlen=5)
    assert buf.size == 0
    assert buf.get_latest(3) == []

    # 推入 3 帧
    for i in range(3):
        buf.push(np.ones((480, 640, 3), dtype=np.uint8) * i)

    assert buf.size == 3
    assert len(buf.get_latest(3)) == 3
    assert buf.get_latest(4) == []  # 不足 4 帧
    print("test_basic passed")


def test_overflow():
    buf = FrameBuffer(maxlen=3)
    for i in range(5):
        buf.push(np.full((100, 100, 3), i, dtype=np.uint8))

    assert buf.size == 3
    frames = buf.get_latest(3)
    assert len(frames) == 3
    # 应该保留最后 3 帧: 2, 3, 4
    assert frames[0][0, 0, 0] == 2
    assert frames[1][0, 0, 0] == 3
    assert frames[2][0, 0, 0] == 4
    print("test_overflow passed")


def test_thread_safety():
    import threading
    import time

    buf = FrameBuffer(maxlen=100)
    errors = []

    def writer():
        for i in range(200):
            buf.push(np.full((10, 10, 3), i, dtype=np.uint8))
            time.sleep(0.001)

    def reader():
        for _ in range(200):
            frames = buf.get_latest(4)
            if frames:
                for f in frames:
                    if f.shape != (10, 10, 3):
                        errors.append("shape mismatch")
                    break
            time.sleep(0.001)

    t1 = threading.Thread(target=writer)
    t2 = threading.Thread(target=reader)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert len(errors) == 0, f"thread safety errors: {errors}"
    print("test_thread_safety passed")


if __name__ == "__main__":
    test_basic()
    test_overflow()
    test_thread_safety()
    print("All F2a tests passed!")
