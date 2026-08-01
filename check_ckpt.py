import torch

ckpt = torch.load("E:/work_space/dynamic_gesture_system/weights/dste_net.pth", map_location="cpu", weights_only=False)
print("Top keys:", list(ckpt.keys()))

sd = ckpt.get("state_dict", ckpt)
keys = list(sd.keys())
print("State keys count:", len(keys))
print("First 3:", keys[:3])
print("Has module. prefix:", keys[0].startswith("module."))
