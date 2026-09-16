"""手工诊断：检查权重文件的结构能否对上当前模型

在服务器上换了一份新权重、或者怀疑权重和代码不匹配时跑这个：
    python tests/check_weights.py

它只做"结构层面"的判定（键数量、module. 前缀、能否严格加载）。
（这是旧版根目录 check_ckpt.py 的修正版——那个脚本硬编码了
weights/dste_net.pth，而这个文件早已改名，跑起来必然报错。）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch

from src import config


def main():
    path = config.MODEL_WEIGHTS_PATH
    print(f"权重文件: {path}")
    if not os.path.exists(path):
        print("✗ 文件不存在")
        return 1
    print(f"  体积: {os.path.getsize(path) / 1024 / 1024:.1f} MB")

    try:
        ckpt = torch.load(path, map_location="cpu", weights_only=False)
    except Exception as e:                       # noqa: BLE001
        print(f"✗ 读取失败: {e}")
        return 1

    sd = ckpt.get("state_dict", ckpt) if isinstance(ckpt, dict) else ckpt
    keys = list(sd.keys())
    print(f"  顶层键: {list(ckpt.keys())[:5] if isinstance(ckpt, dict) else '(非 dict)'}")
    print(f"  参数张量数: {len(keys)}")
    print(f"  module. 前缀（DataParallel 训练留下的）: {keys[0].startswith('module.')}")

    from src.core.inference import GestureRecognizer
    r = GestureRecognizer()
    print(f"\n加载结果: {r.status}")
    if r.status != "ok":
        print(f"  {r.status_detail}")
        return 1
    print("✓ 结构与 checkpoint 严格对齐，可以直接用")
    return 0


if __name__ == "__main__":
    sys.exit(main())
