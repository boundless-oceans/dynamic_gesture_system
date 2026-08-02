# DSTE-Net 动态手势识别系统

基于 DSTE-Net 的实时动态手势识别桌面应用，非遗展示系统。

## 一、功能
- 摄像头实时预览 + 手势实时识别（8帧滑动窗口）
- 手势驱动页面导航（swipe/click/palm/zoom/circle）
- 首页：6项非遗轮播 + 印章 + 回纹分隔线
- 详情页：项目介绍 + 视频区 + 图片区
- 3D查看：Three.js 模型交互
- 传承人风采：上下切换展示
- 设置页：手势对照表
- 置信度显示 + 墨韵粒子背景 + 毛玻璃UI + 启动画面

## 二、快速开始

### 安装
```bash
# venv
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt

# conda
conda env create -f environment.yml && conda activate gesture
```

### 运行
```bash
python main.py
```

## 三、参考
- DSTE-Net 论文
- TSM: arXiv:1811.08383
- EgoGesture 83类
