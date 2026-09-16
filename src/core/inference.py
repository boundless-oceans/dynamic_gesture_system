"""模型加载 + 推理"""

import os
import torch
import torchvision.transforms as T
from PIL import Image
import numpy as np
from PySide6.QtCore import QThread, Signal

from src.model.models import TSN
from src.model.transforms import GroupScale, GroupCenterCrop, Stack, ToTorchFormatTensor, GroupNormalize
from src import config


class GestureRecognizer:
    """DSTE-Net 手势识别器"""

    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        print(f"[Inference] Using device: {self.device}")

        self.model = self._build_model()
        self._load_weights()
        self.model.to(self.device)
        self.model.eval()

        self.transform = self._build_transform()

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
        """加载权重，不存在则使用随机初始化"""
        if os.path.exists(config.MODEL_WEIGHTS_PATH):
            print(f"[Inference] Loading weights from {config.MODEL_WEIGHTS_PATH}")
            checkpoint = torch.load(config.MODEL_WEIGHTS_PATH, map_location=self.device, weights_only=False)
            sd = checkpoint.get('state_dict', checkpoint)
            # 模型结构与 checkpoint 严格对齐（DSTE + ECA），module. 前缀来自 DataParallel 训练
            self.model.load_state_dict(
                {k.replace('module.', ''): v for k, v in sd.items()}, strict=True)
            print("[Inference] Weights loaded.")
        else:
            print(f"[WARNING] No weights found at {config.MODEL_WEIGHTS_PATH}")
            print("[WARNING] Using random initialized model (predictions will be meaningless)")

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

    def predict(self, frames: list) -> dict:
        """
        推理单次
        frames: list of 8 numpy arrays
        returns: {"gesture": str, "confidence": float, "top3": [(label, prob), ...]}
        """
        with torch.no_grad():
            input_tensor = self.preprocess(frames).to(self.device)
            output = self.model(input_tensor)       # (1, num_classes)
            probs = torch.softmax(output, dim=1)     # (1, num_classes)
            top3_prob, top3_idx = torch.topk(probs, k=3, dim=1)

        results = {
            "gesture": str(top3_idx[0, 0].item()),
            "confidence": round(top3_prob[0, 0].item(), 4),
            "top3": [
                (str(top3_idx[0, i].item()), round(top3_prob[0, i].item(), 4))
                for i in range(3)
            ]
        }
        return results


class InferenceThread(QThread):
    """推理线程：定时从帧缓冲取帧，送入模型推理"""

    result_ready = Signal(dict)  # {"gesture": str, "confidence": float, "top3": list}

    def __init__(self, frame_buffer, recognizer: GestureRecognizer):
        super().__init__()
        self.frame_buffer = frame_buffer
        self.recognizer = recognizer
        self._running = False

    def run(self):
        self._running = True
        while self._running:
            frames = self.frame_buffer.get_latest(config.NUM_SEGMENTS)
            if len(frames) == config.NUM_SEGMENTS:
                result = self.recognizer.predict(frames)
                self.result_ready.emit(result)
            self.msleep(config.INFERENCE_INTERVAL_MS)

    def stop(self):
        self._running = False
        self.wait()
