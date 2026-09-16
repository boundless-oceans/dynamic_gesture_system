"""模型加载 + 推理"""

import os
import time
from collections import deque

import torch
import torchvision.transforms as T
from PIL import Image
import numpy as np
from PySide6.QtCore import QThread, Signal

from src.model.models import TSN
from src.model.transforms import GroupScale, GroupCenterCrop, Stack, ToTorchFormatTensor, GroupNormalize
from src import config


def model_view_rect(frame_w: int, frame_h: int) -> tuple:
    """模型实际能看到画面的哪一块，返回原图坐标 (x, y, w, h)。

    ⚠ 必须与 GestureRecognizer._build_transform 里的预处理一一对应：
      GroupScale(SCALE_SIZE)      —— torchvision.Resize，把**短边**缩到 SCALE_SIZE
      GroupCenterCrop(INPUT_SIZE) —— 再取中心 INPUT_SIZE 见方
    所以模型看不到画面四周。实测 640x480 下约等于中央 420x420（x:109~530, y:29~450）。
    改了预处理参数就必须同步这里，否则预览上的交互区框会画偏。
    （tests/test_interaction_zone.py 用真实预处理管线校验了这层对应关系。）
    """
    short = min(frame_w, frame_h)
    if short <= 0:
        return (0.0, 0.0, float(frame_w), float(frame_h))
    k = config.SCALE_SIZE / float(short)          # 短边缩放比
    w = min(float(frame_w), config.INPUT_SIZE / k)
    h = min(float(frame_h), config.INPUT_SIZE / k)
    return ((frame_w - w) / 2.0, (frame_h - h) / 2.0, w, h)


class GestureRecognizer:
    """DSTE-Net 手势识别器"""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[Inference] Using device: {self.device}")

        self.transform = self._build_transform()
        # 概率平滑缓冲：存放最近几次的 softmax
        self._prob_win = deque(maxlen=max(1, config.SMOOTH_FRAMES))

        # 后端选择：优先 ONNX Runtime(CPU)，否则回退 PyTorch
        self.model = None
        self._ort = None
        # 权重状态：ok / missing / error:<原因>。非 ok 时不应启用推理
        # （随机初始化的模型照样输出"看着挺像"的置信度，静默错误最难排查）
        self.status = "ok"
        self.status_detail = ""
        if config.USE_ONNX and os.path.exists(config.ONNX_MODEL_PATH):
            try:
                import onnxruntime as ort
                self._ort = ort.InferenceSession(
                    config.ONNX_MODEL_PATH, providers=['CPUExecutionProvider'])
                print(f"[Inference] Using ONNX Runtime (CPU): {config.ONNX_MODEL_PATH}")
            except Exception as e:
                print(f"[Inference] ONNX 加载失败，回退 PyTorch: {e}")
        if self._ort is None:
            self.model = self._build_model()
            self._load_weights()
            self.model.to(self.device)
            self.model.eval()

    def _build_model(self):
        """构建 TSN + DSTE 模型"""
        print(f"[Inference] Building TSN model: {config.ARCH}, segments={config.NUM_SEGMENTS}")
        return TSN(
            num_class=config.NUM_CLASSES,
            num_segments=config.NUM_SEGMENTS,
            modality='RGB',
            base_model=config.ARCH,
            consensus_type='avg',
            dropout=0.5,
            is_shift=True,
            shift_div=0.5,
            shift_place='blockres',
        )

    def _load_weights(self):
        """加载权重。失败时记录到 self.status，由入口提示——绝不静默地用随机权重跑。"""
        if not os.path.exists(config.MODEL_WEIGHTS_PATH):
            print(f"[WARNING] No weights found at {config.MODEL_WEIGHTS_PATH}")
            self.status = "missing"
            self.status_detail = config.MODEL_WEIGHTS_PATH
            return
        print(f"[Inference] Loading weights from {config.MODEL_WEIGHTS_PATH}")
        try:
            checkpoint = torch.load(config.MODEL_WEIGHTS_PATH, map_location=self.device, weights_only=False)
            sd = checkpoint.get('state_dict', checkpoint)
            # 模型结构与 checkpoint 严格对齐（DSTE + ECA），module. 前缀来自 DataParallel 训练
            self.model.load_state_dict(
                {k.replace('module.', ''): v for k, v in sd.items()}, strict=True)
        except Exception as e:
            print(f"[ERROR] 权重加载失败: {e}")
            self.status = "error"
            self.status_detail = str(e)
            return
        print("[Inference] Weights loaded.")

    def _build_transform(self):
        """构建预处理 pipeline"""
        return T.Compose([
            GroupScale(config.SCALE_SIZE),
            GroupCenterCrop(config.INPUT_SIZE),
            Stack(roll=False),
            ToTorchFormatTensor(div=True),
            GroupNormalize(config.INPUT_MEAN, config.INPUT_STD),
        ])

    def preprocess(self, frames: list) -> torch.Tensor:
        """
        预处理 8 帧 numpy 图像 → 模型输入 tensor
        frames: list of 8 numpy arrays (H, W, 3)
        returns: tensor (1, 24, 224, 224)
        """
        pil_frames = [Image.fromarray(f) for f in frames]
        tensor = self.transform(pil_frames)  # (24, 224, 224)
        return tensor.unsqueeze(0)           # (1, 24, 224, 224)

    def reset_smoothing(self):
        """清空概率平滑缓冲。动静门控恢复推理时调用：
        缓冲里留的是静止之前的旧概率，不丢掉会把恢复后的结果稀释掉。"""
        self._prob_win.clear()

    def predict(self, frames: list) -> dict:
        """
        推理单次（结果经最近 SMOOTH_FRAMES 次 softmax 平均平滑）
        frames: list of 8 numpy arrays
        returns: {"gesture": str, "confidence": float, "top3": [(label, prob), ...]}
        """
        if self._ort is not None:
            inp = self.preprocess(frames).numpy()          # (1,24,224,224) float32
            out = self._ort.run(None, {self._ort.get_inputs()[0].name: inp})[0]
            logits = torch.from_numpy(out)
        else:
            with torch.inference_mode():
                logits = self.model(self.preprocess(frames).to(self.device))

        with torch.inference_mode():
            probs = torch.softmax(logits, dim=1)        # (1, num_classes)

            # 即时结果（显示用，跟手）
            raw_conf, raw_idx = torch.max(probs, dim=1)

            # 平滑结果（触发用，稳定）
            self._prob_win.append(probs)
            smoothed = torch.stack(list(self._prob_win), dim=0).mean(0)
            top3_prob, top3_idx = torch.topk(smoothed, k=3, dim=1)

        results = {
            "gesture": str(top3_idx[0, 0].item()),
            "confidence": round(top3_prob[0, 0].item(), 4),
            "top3": [
                (str(top3_idx[0, i].item()), round(top3_prob[0, i].item(), 4))
                for i in range(3)
            ],
            # 显示用即时预测（不平滑）
            "raw_gesture": str(raw_idx[0].item()),
            "raw_confidence": round(raw_conf[0].item(), 4),
        }
        return results


class InferenceThread(QThread):
    """推理线程：定时从帧缓冲取帧，送入模型推理

    长时间识别不到手势时按 IDLE_LADDER 逐档降低推理频率（空闲降频）。
    """

    result_ready = Signal(dict)  # {"gesture": str, "confidence": float, "top3": list}

    def __init__(self, frame_buffer, recognizer: GestureRecognizer):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.recognizer = recognizer
        self._running = False
        # 最近一次"识别到手势"的时刻（毫秒）。空闲降频就按它算空闲了多久。
        self._last_active_ms = time.time() * 1000.0

    # ---- 空闲降频 ----
    def mark_active(self):
        """外部（如重开摄像头）调用：把空闲计时清零，立刻回到全速档"""
        self._last_active_ms = time.time() * 1000.0

    def idle_ms(self) -> float:
        return time.time() * 1000.0 - self._last_active_ms

    def ladder_step(self) -> int:
        """当前处于阶梯的第几档（0 = 全速）。空闲越久档位越深。"""
        if not config.IDLE_LADDER_ENABLED or not config.IDLE_LADDER:
            return 0
        idle = self.idle_ms()
        step = 0
        for i, (threshold_ms, _) in enumerate(config.IDLE_LADDER):
            if idle >= threshold_ms:
                step = i
        return step

    def interval_ms(self, step: int) -> int:
        """该档对应的推理间隔（毫秒）"""
        if not config.IDLE_LADDER:
            return config.INFERENCE_INTERVAL_MS
        return config.IDLE_LADDER[min(step, len(config.IDLE_LADDER) - 1)][1]

    def run(self):
        self._running = True
        self.mark_active()
        fails = 0
        step = 0
        while self._running:
            # 单次推理异常不能终止线程：否则界面一切正常、只有手势永久失效，
            # 展台上最难排查的一种故障。这里跳过该帧继续跑。
            try:
                new_step = self.ladder_step()
                if new_step < step:
                    # 从深档回到浅档（空闲够了又活跃起来）：平滑缓冲里是上次
                    # 空闲前的旧概率，留着会稀释掉恢复后的第一条结果
                    self.recognizer.reset_smoothing()
                if new_step != step:
                    print("[Inference] 空闲 %d 秒，推理间隔 %d ms"
                          % (self.idle_ms() / 1000, self.interval_ms(new_step)), flush=True)
                    step = new_step

                window = self.frame_buffer.get_latest(config.SAMPLE_WINDOW_FRAMES)
                if len(window) < config.SAMPLE_WINDOW_FRAMES:
                    # 没有帧（摄像头刚启动/已关闭）不能算"空闲"——没数据不等于没人。
                    # 否则启动时摄像头探测那几秒会把档位白白降下去。
                    self.mark_active()
                # 攒满整个采样窗口（约 0.5s @30fps）再开始预测
                elif len(window) == config.SAMPLE_WINDOW_FRAMES:
                    # 在窗口内均匀抽 NUM_SEGMENTS 帧（旧→新），铺开时间跨度
                    idx = np.linspace(0, len(window) - 1, config.NUM_SEGMENTS).round().astype(int)
                    clip = [window[i] for i in idx]
                    res = self.recognizer.predict(clip)
                    # 识别到手势 → 立刻回到全速档（用即时的 raw 置信度，比平滑值
                    # 反应更快；判据与触发门槛同一个值，空场景实测从不达标）
                    if res.get("raw_confidence", 0.0) >= config.CONFIDENCE_THRESHOLD:
                        self._last_active_ms = time.time() * 1000.0
                    # 始终发送（显示用）；触发与否由主窗口按置信度门槛决定
                    self.result_ready.emit(res)
                if fails:
                    print(f"[Inference] 已恢复正常（此前连续异常 {fails} 次）", flush=True)
                    fails = 0
            except Exception as e:
                fails += 1
                if fails == 1 or fails % 50 == 0:
                    print(f"[Inference] 推理异常（第 {fails} 次），跳过该帧继续: {e}", flush=True)
            self.msleep(self.interval_ms(step))

    def stop(self):
        self._running = False
        self.wait()
