"""图像预处理变换（仅推理用）"""

import torchvision
import numpy as np
import torch
from PIL import Image


class GroupScale:
    """缩放到指定尺寸（短边对齐）"""
    def __init__(self, size, interpolation=Image.BILINEAR):
        self.worker = torchvision.transforms.Resize(size, interpolation)

    def __call__(self, img_group):
        return [self.worker(img) for img in img_group]


class GroupCenterCrop:
    """中心裁剪"""
    def __init__(self, size):
        self.worker = torchvision.transforms.CenterCrop(size)

    def __call__(self, img_group):
        return [self.worker(img) for img in img_group]


class Stack:
    """沿通道拼接多帧"""
    def __init__(self, roll=False):
        self.roll = roll

    def __call__(self, img_group):
        if self.roll:
            return np.concatenate([np.array(x)[:, :, ::-1] for x in img_group], axis=2)
        return np.concatenate(img_group, axis=2)


class ToTorchFormatTensor:
    """numpy/tensor → torch.FloatTensor，归一化到 [0, 1]"""
    def __init__(self, div=True):
        self.div = div

    def __call__(self, pic):
        if isinstance(pic, np.ndarray):
            img = torch.from_numpy(pic).permute(2, 0, 1).contiguous()
        else:
            img = torch.ByteTensor(torch.ByteStorage.from_buffer(pic.tobytes()))
            img = img.view(pic.size[1], pic.size[0], len(pic.mode))
            img = img.transpose(0, 1).transpose(0, 2).contiguous()
        return img.float().div(255) if self.div else img.float()


class GroupNormalize:
    """均值方差归一化"""
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std

    def __call__(self, tensor):
        rep_mean = self.mean * (tensor.size()[0] // len(self.mean))
        rep_std = self.std * (tensor.size()[0] // len(self.std))
        for t, m, s in zip(tensor, rep_mean, rep_std):
            t.sub_(m).div_(s)
        return tensor


