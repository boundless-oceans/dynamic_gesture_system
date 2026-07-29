# DSTE-Net 动态手势识别系统 - 项目状态

## 项目概述

基于 DSTE-Net 的实时动态手势识别桌面应用，用于非遗展示系统的动态手势控制。
技术栈：PySide6 + OpenCV + PyTorch
模型：ResNet-50 + DSTE 模块（LSTE + GSTE），输入 8 帧 RGB，输出 83 类 EgoGesture 手势

## 功能清单

### P0（核心功能）- 全部完成

| 编号 | 功能 | 描述 | 状态 |
|------|------|------|:--:|
| F2b | 模型加载与推理 | DSTE-Net 模型构建、权重加载、predict() 接口 | 已完成 |
| F2a | 帧缓冲队列 | 线程安全环形队列，保持最近 N 帧，支持取 8 帧 | 已完成 |
| F1 | 摄像头预览 | OpenCV 采集 -> QThread -> 画面显示 | 已完成 |
| F2 | 推理线程 | 从帧缓冲取 8 帧 -> 预处理 -> 推理 -> emit 结果信号 | 已完成 |
| F7 | 手势映射 | 83 类 DSTE-Net 输出 -> 9 种控制手势 | 已完成 |
| F4 | 主窗口 | 4 页框架 + 页面切换 + 摄像头悬浮窗 + 手势路由 + 去抖 | 已完成 |
| F0 | 应用入口 | main.py，启动 QApplication | 已完成 |

### P1（页面内容）

| 编号 | 功能 | 描述 | 状态 |
|------|------|------|:--:|
| F8 | 首页 | 渐变背景、6 项轮播、单击选中双击进入、关闭摄像头 | 已完成 |
| F9 | 详情页 | 非遗项目图文介绍，上下滚动 | 已完成 |
| F10 | 3D 查看 | Three.js 3D 模型交互（旋转、缩放） | 已完成 |
| F5 | 去抖 | 连续 N 次识别结果一致才触发操作 | 已完成（内置） |
| F3 | 置信度显示 | 摄像头小窗旁显示当前手势 + 置信度 | 待实现 |

### P2（锦上添花）

| 编号 | 功能 | 描述 | 状态 |
|------|------|------|:--:|
| F11 | 设置页 | 手势列表对照表 | 待实现 |
| F6 | 标签映射 | 83 类英文 -> 中文，gestures.json | 待实现 |

## 实现顺序

已完成: F2b -> F2a -> F1 -> F2 -> F7 -> F4 -> F0 -> F8

接下来: F9 -> F10 -> F3 -> F11 -> F6

## 当前进度

- P0 全部完成
- P1 已完成首页(F8)，去抖(F5)已内置
- 模型权重文件尚未训练，当前使用随机初始化占位
- 项目路径：E:\work_space\dynamic_gesture_system

## 已完成功能详情

### F2b: 模型加载与推理

文件: src/core/inference.py
类: GestureRecognizer

| 方法 | 调用方 | 描述 |
|------|------|------|
| __init__() | 应用启动 | 构建 TSN + DSTE 模型，加载权重，构建预处理 pipeline |
| _build_model() | __init__ | 创建 TSN(num_class, num_segments=8, ResNet-50, DSTE) |
| _load_weights() | __init__ | 从 weights/ 加载 .pth，不存在则随机初始化 |
| _build_transform() | __init__ | 推理预处理: Scale(256) -> CenterCrop(224) -> Stack -> ToTensor -> Normalize |
| preprocess(frames) | predict | 8 帧 numpy(H,W,3) -> tensor(1,24,224,224) |
| predict(frames) | 推理线程 | 推理一次，返回 {"gesture", "confidence", "top3"} |

文件: src/model/models.py
类: TSN(nn.Module)

| 方法 | 描述 |
|------|------|
| __init__() | ResNet-50 backbone + DSTE 模块 + 分类头 |
| forward(input) | (B, 24, 224, 224) -> (B, num_class) |

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
| __init__(maxlen=32) | 应用启动 | 初始化 deque 环形缓冲 |
| push(frame) | 摄像头线程 | 存入一帧 numpy 数组，线程安全 |
| get_latest(n) | 推理线程 | 取最近 n 帧，不足返回 []，线程安全 |
| size | 任意 | 属性，当前缓冲帧数 |
| clear() | 任意 | 清空缓冲 |

### F1: 摄像头预览

文件: src/core/camera.py
类: CameraThread(QThread)

| 方法/信号 | 调用方 | 描述 |
|------|------|------|
| run() | 自动 | 采集循环: BGR->RGB, 镜像, 存共享区, 推 FrameBuffer |
| get_frame() | UI 定时器 | 主线程安全读取当前帧 |
| stop() | UI | 停止采集并等待线程退出 |
| frame_ready (Signal) | CameraWidget | 通知 UI 有新帧可读 |

文件: src/ui/camera_widget.py
类: CameraWidget(QWidget)

| 方法 | 调用方 | 描述 |
|------|------|------|
| start(frame_buffer) | 外部 | 启动 CameraThread + 33ms 定时器 |
| stop() | 外部 | 停止采集，显示"摄像头未开启" |
| _update_frame() | QTimer | 从 CameraThread 取帧 -> QPixmap -> QLabel |

### F2: 推理线程

文件: src/core/inference.py
类: InferenceThread(QThread)

| 方法/信号 | 调用方 | 描述 |
|------|------|------|
| run() | 自动 | 每 200ms 从 FrameBuffer 取 8 帧 -> predict() -> emit result_ready |
| stop() | UI | 停止推理循环 |
| result_ready (Signal) | MainWindow | 发射推理结果 dict |

### F7: 手势映射

文件: src/core/gesture_mapper.py

| 元素 | 描述 |
|------|------|
| EGO_TO_CONTROL | 字典：原始标签 -> 控制手势（10条映射） |
| CONTROL_GESTURES | 集合：9 种控制手势名 |
| map_gesture(label) | 原始标签 -> 控制手势，未映射返回 None |
| index_to_control(idx) | 索引 -> 控制手势 |

### F4 + F8: 主窗口与首页

文件: src/ui/main_window.py
类: MainWindow(QMainWindow)

| 方法/属性 | 描述 |
|------|------|
| stack | QStackedWidget，4 页：首页/详情/3D/设置 |
| camera_widget | 右上角悬浮，320x240，可显隐 |
| signal_gesture_action | 手势操作分发信号 |
| _on_control_gesture() | 手势路由：首页/详情/3D 各自响应，含去抖 |
| _toggle_camera() | 关闭/打开摄像头 + 按钮文字切换 |

文件: src/ui/home_page.py
类: HomePage(QWidget)

| 方法 | 描述 |
|------|------|
| paintEvent() | 绘制白->蓝渐变背景 |
| _prev() / _next() | 左右箭头切换选中项（仅高亮，不跳转） |
| _ItemCard | 单击选中 + 双击进入，选中时变大+橙色边框 |
| btn_camera | 关闭/打开摄像头按钮 |