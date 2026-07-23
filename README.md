# DSTE-Net 动态手势识别系统

基于 DSTE-Net（Dual-scale Spatial-Temporal Excitation Network）的实时动态手势识别桌面应用。

## 一、功能

- 摄像头实时画面预览
- 动态手势实时识别（基于 8 帧滑动窗口）
- 识别结果展示（手势类别 + 置信度）
- Top-3 候选结果展示

## 二、目录结构

```
dynamic_gesture_system/
├── README.md                     # 项目说明
├── requirements.txt              # pip 依赖清单
├── environment.yml               # conda 环境配置
├── .gitignore                    # Git 忽略规则
├── .agents                       # AI 协作状态文件
├── main.py                       # 应用入口
│
├── src/                          # 源代码
│   ├── config.py                 # 全局配置（模型路径、手势标签等）
│   │
│   ├── ui/                       # 界面层
│   │   ├── main_window.py        # 主窗口
│   │   ├── camera_widget.py      # 摄像头画面组件
│   │   └── result_panel.py       # 识别结果面板
│   │
│   ├── core/                     # 核心逻辑层
│   │   ├── camera.py             # 摄像头采集线程
│   │   ├── frame_buffer.py       # 环形帧缓冲队列
│   │   └── inference.py          # 模型推理线程
│   │
│   └── model/                    # DSTE-Net 模型定义
│       ├── models.py             # TSN 网络主体
│       ├── temporal_module.py    # DSTE 时空激励模块（核心）
│       ├── basic_ops.py          # 基础操作
│       └── transforms.py         # 图像预处理变换
│
├── weights/                      # 模型权重文件（.gitignore）
│   └── dste_net.pth
│
└── assets/                       # 静态资源
    └── gestures.json             # 手势标签中英文对照
```

## 三、系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    PySide6 桌面应用                       │
│                                                         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   UI 层      │    │   Core 层   │    │  Model 层   │  │
│  │             │    │             │    │             │  │
│  │ main_window │◀───│  camera     │───▶│ TSN 网络    │  │
│  │ camera_widget│   │  frame_buf  │    │ DSTE 模块   │  │
│  │ result_panel│    │  inference  │    │ transforms  │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│         │                  │                  │         │
│         └──────── PySide6 Signal/Slot ────────┘         │
└─────────────────────────────────────────────────────────┘
```

## 四、数据流

```
                        ┌──────────────┐
    摄像头 ────────────▶│ CameraThread │  30fps 采集
    (OpenCV)            │  (QThread)   │
                        └──────┬───────┘
                               │
                               ▼ 每帧
                        ┌──────────────┐
                        │ FrameBuffer  │  线程安全环形队列
                        │  (deque)     │  保持最近 N 帧
                        └──────┬───────┘
                               │
                               ▼ 每 200ms 取最近 8 帧
                        ┌──────────────┐
                        │InferenceThread│
                        │  (QThread)   │
                        │              │
                        │ 预处理:       │
                        │  Resize 256   │
                        │  CenterCrop   │
                        │  224          │  ┌──────────────┐
                        │  Normalize    │  │ DSTE-Net     │
                        │  ToTensor     │──│ ResNet-50    │
                        │              │  │ LSTE + GSTE  │
                        │ Softmax →     │  │ 83 类输出    │
                        │ Top-3 候选    │  └──────────────┘
                        └──────┬───────┘
                               │
                               ▼ Signal(gesture, confidence, top3)
                        ┌──────────────┐
                        │   UI 主线程   │
                        │              │
                        │  ┌─────────┐ │
                        │  │摄像头画面│ │
                        │  └─────────┘ │
                        │  ┌─────────┐ │
                        │  │手势类别  │ │
                        │  │置信度条  │ │
                        │  │Top3 列表 │ │
                        │  └─────────┘ │
                        └──────────────┘
```

## 五、快速开始

### 环境要求

- Python >= 3.9
- 摄像头（笔记本自带或 USB 外接均可）

### 安装

**方式一：venv + pip**

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate      # Windows
# source venv/bin/activate # Linux/macOS

# 安装依赖
pip install -r requirements.txt
```

**方式二：Conda**

```bash
# 从 environment.yml 创建环境
conda env create -f environment.yml

# 激活环境
conda activate gesture
```

### 运行

```bash
python main.py
```

## 六、手势类别

系统支持 83 种动态手势（基于 EgoGesture 数据集），包括：

- 方向滑动：向上/向下/向左/向右滑动
- 缩放操作：放大、缩小
- 手指动作：点击、双击、长按
- 画圈、打钩、打叉 等

> 完整列表见 `assets/gestures.json`

## 七、参考

- DSTE-Net 论文：Dual-scale Spatial-Temporal Excitation Network for Dynamic Gesture Recognition
- TSM 框架：Temporal Shift Module for Efficient Video Understanding (arXiv:1811.08383)
- 数据集：EgoGesture（83类手势）
