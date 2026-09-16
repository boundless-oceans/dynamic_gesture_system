"""动静门控：画面没动作时跳过推理

展台绝大多数时间没人在做手势，而一次推理要几百毫秒。这里用"帧间差异"
这个极便宜的判据把静止时段挡掉，动作一出现立刻恢复推理——**延迟不变**，
省下的算力正比于空闲时间占比，跟推理本身快慢无关
（所以它在慢机器上和快机器上一样有效，这点和"拉长推理间隔"相反）。

判定放在摄像头线程：它本来就有帧，而且大部分时间阻塞在 cap.read() 上，
顺便算一次几乎不占额外成本。推理线程只读一个时间戳。
"""
import threading
import time

import cv2
import numpy as np

# 差异检测的工作分辨率：只用来判断"有没有动"，不需要看清细节
#
# 这几个值是拿真实摄像头实测标定的（静止画面连拍 180 帧统计"变化像素数"）：
#   - 不滤波直接比：中位就有 117 个像素变化 >12 灰度，最大 863 —— 那点噪声
#     会让门控永远关不掉（实测 15.7% 的静止帧被误判成"有动作"）。
#   - 先做 5x5 高斯模糊再比：噪声几乎归零，80x60 下最大只有 10 个像素。
# 另外摄像头刚打开的头两三秒自动曝光在漂移，那段时间会一直判"有动作"——
# 这是安全的默认方向（多推理总比漏掉手势好），不用特殊处理。
_ANALYSIS_SIZE = (80, 60)
# 先模糊掉传感器噪声再比，否则噪声本身就能撑开阈值
_BLUR_KSIZE = (5, 5)
# 像素灰度差超过多少算"这个像素变了"
_PIXEL_DELTA = 12


class MotionGate:
    """判断画面里有没有动作。线程安全：摄像头线程 feed()，推理线程 active()。"""

    def __init__(self, enabled: bool = True, grace_ms: int = 2500,
                 threshold: float = 0.002, time_fn=time.time):
        """
        enabled:  False 时 active() 恒为 True（等于关掉门控）
        grace_ms: 最后一次动作之后，还继续认为"有动作"多久。
                  这段宽限期是为了让"松手解锁"（置信度掉下来 → 清锁）仍能生效。
        threshold: 变化像素占比超过它才算有动作。默认 0.004 ≈ 80x60 里的 19 个像素，
                   约为实测静止噪声（同规格下最大 10 个像素）的 2 倍，
                   对应原图 640x480 里约 45x45 像素的变化。
                   取值偏敏感是刻意的——太钝会让手势被误挡（那是功能坏了），
                   太灵只是省不下多少算力（那是性能差一点），两者代价不对称。
        """
        self.enabled = enabled
        self.grace_ms = grace_ms
        self.threshold = threshold
        self._min_pixels = max(1, int(threshold * _ANALYSIS_SIZE[0] * _ANALYSIS_SIZE[1]))
        self._time = time_fn
        self._prev = None
        # 初始按"有动作"处理，否则启动瞬间（还没喂过帧）会被判成静止。
        # 拿到第一帧后由 feed() 接管。
        self._last_motion_ms = self._time() * 1000.0
        self._lock = threading.Lock()
        # 统计（便于现场判断门控是否过于灵敏/迟钝）
        self.frames_seen = 0
        self.motion_frames = 0

    def feed(self, frame_rgb: np.ndarray):
        """摄像头线程每帧调用：算出这一帧相对上一帧有没有动"""
        if not self.enabled:
            return
        try:
            small = cv2.resize(frame_rgb, _ANALYSIS_SIZE, interpolation=cv2.INTER_AREA)
            gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
            gray = cv2.GaussianBlur(gray, _BLUR_KSIZE, 0)
        except Exception:
            return                      # 帧异常不该拖垮采集线程
        now_ms = self._time() * 1000.0
        with self._lock:
            self.frames_seen += 1
            prev, self._prev = self._prev, gray
            if prev is None:
                # 首帧没有参照物，按"有动作"处理，避免启动瞬间被挡住
                self._last_motion_ms = now_ms
                return
            diff = cv2.absdiff(gray, prev)
            changed = int(np.count_nonzero(diff > _PIXEL_DELTA))
            if changed >= self._min_pixels:
                self._last_motion_ms = now_ms
                self.motion_frames += 1

    def active(self) -> bool:
        """推理线程问：现在该不该推理？（门控关闭时恒为 True）"""
        if not self.enabled:
            return True
        with self._lock:
            last = self._last_motion_ms
        return (self._time() * 1000.0 - last) < self.grace_ms

    def motion_ratio(self) -> float:
        """有动作的帧占比，仅供诊断"""
        with self._lock:
            return (self.motion_frames / self.frames_seen) if self.frames_seen else 0.0

    def reset(self):
        """摄像头重启后调用：丢掉旧参照帧，避免拿关摄像头前后的两帧相比"""
        with self._lock:
            self._prev = None
            self._last_motion_ms = self._time() * 1000.0
            self.frames_seen = 0
            self.motion_frames = 0
