# DSTE-Net 动态手势识别系统 - 项目状态

## 项目概述
基于 DSTE-Net 的实时动态手势识别桌面应用。
技术栈：PySide6 + OpenCV + PyTorch
模型：ResNet-50 + DSTE 模块（LSTE + GSTE），输入 8 帧 RGB，输出 83 类手势

## 功能清单

### P0（核心功能）

| 编号 | 功能 | 描述 | 状态 |
|------|------|------|:--:|
| F2b | 模型加载与推理 | DSTE-Net 模型构建、权重加载、predict() 接口 | 已完成 |
| F2a | 帧缓冲队列 | 线程安全环形队列，保持最近 N 帧，支持取 8 帧 | 已完成 |
| F1 | 摄像头预览 | OpenCV 采集 → QThread → 画面显示 | 已完成 |
| F2 | 推理线程 | 从帧缓冲取 8 帧 → 预处理 → 推理 → emit 结果信号 | 待实现 |
| F3 | 结果展示 | 手势类别 + 置信度进度条 + Top-3 列表 | 待实现 |
| F4 | 主窗口 | 组装 F1 + F3，信号槽串联 | 待实现 |
| F0 | 应用入口 | main.py，启动 QApplication | 待实现 |

### P1（增强功能）

| 编号 | 功能 | 描述 | 状态 |
|------|------|------|:--:|
| F5 | 去抖 | 连续 N 次识别结果一致才输出 | 待实现 |
| F6 | 标签映射 | 83 类英文标签 → 中文，gestures.json | 待实现 |

## 实现顺序
F2b → F2a → F1 → F2 → F3 → F4 → F0 → F5 → F6

## 当前进度
- 已完成 F2b（模型加载与推理）
- 已完成 F2a（帧缓冲队列）
- 模型权重文件尚未训练，当前使用随机初始化占位
- 项目路径：E:\work_space\dynamic_gesture_system

## 已完成功能详情

### F2b: 模型加载与推理

文件: src/core/inference.py
类: GestureRecognizer

| 方法 | 调用方 | 描述 |
|------|------|------|
| `__init__()` | 应用启动 | 构建 TSN + DSTE 模型，加载权重，构建预处理 pipeline |
| `_build_model()` | `__init__` | 创建 TSN(num_class, num_segments=8, ResNet-50, DSTE) |
| `_load_weights()` | `__init__` | 从 weights/ 加载 .pth，不存在则随机初始化 |
| `_build_transform()` | `__init__` | 推理预处理: Scale(256) -> CenterCrop(224) -> Stack -> ToTensor -> Normalize |
| `preprocess(frames)` | `predict` | 8 帧 numpy(H,W,3) -> tensor(1,24,224,224) |
| `predict(frames)` | 推理线程 | 推理一次，返回 {"gesture", "confidence", "top3"} |

文件: src/model/models.py
类: TSN(nn.Module)

| 方法 | 描述 |
|------|------|
| `__init__()` | ResNet-50 backbone + DSTE 模块 + 分类头 |
| `forward(input)` | (B, 24, 224, 224) -> (B, num_class) |

文件: src/model/temporal_module.py

| 类/函数 | 描述 |
|------|------|
| CoordAtt | 坐标注意力 (LSTE 组件) |
| SpatialAttention | 空间自注意力 (GSTE 组件) |
| TemporalModule | DSTE 模块包装器 (LSTE + GSTE) |
| make_temporal_module() | 将 DSTE 注入 ResNet 各层残差块 |

文件: src/model/transforms.py

| 类 | 描述 |
|------|------|
| GroupScale | 缩放到短边 256 |
| GroupCenterCrop | 中心裁剪 224 |
| Stack | 沿通道拼接多帧 |
| ToTorchFormatTensor | numpy -> torch, /255 |
| GroupNormalize | mean/std 归一化 |

文件: src/model/basic_ops.py

| 类 | 描述 |
|------|------|
| ConsensusModule | segment 维度 avg pooling |

### F2a: 帧缓冲队列

文件: src/core/frame_buffer.py
类: FrameBuffer

| 方法 | 调用方 | 描述 |
|------|------|------|
| `__init__(maxlen=32)` | 应用启动 | 初始化 deque 环形缓冲 |
| `push(frame)` | 摄像头线程 | 存入一帧 numpy 数组，线程安全 |
| `get_latest(n)` | 推理线程 | 取最近 n 帧，不足返回 []，线程安全 |
| `size` | 任意 | 属性，当前缓冲帧数 |
| `clear()` | 任意 | 清空缓冲 |

### F1: 摄像头预览

文件: src/core/camera.py
类: CameraThread(QThread)

| 方法/信号 | 调用方 | 描述 |
|------|------|------|
| `run()` | 自动 | 采集循环: BGR->RGB, 镜像, 存共享区, 推 FrameBuffer, emit frame_ready |
| `get_frame()` | UI 定时器 | 主线程安全读取当前帧 |
| `stop()` | UI | 停止采集并等待线程退出 |
| `frame_ready` (Signal) | CameraWidget | 通知 UI 有新帧可读 |

文件: src/ui/camera_widget.py
类: CameraWidget(QWidget)

| 方法 | 调用方 | 描述 |
|------|------|------|
| `start(frame_buffer)` | 外部 | 启动 CameraThread + 30ms 定时器 |
| `stop()` | 外部 | 停止采集和显示 |
| `_update_frame()` | QTimer | 从 CameraThread 取帧 -> QPixmap -> QLabel |
