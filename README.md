# 非遗动态手势展示系统（DSTE-Net）

基于 **DSTE-Net**（ResNet-50 + 时空激励模块）的实时动态手势识别桌面应用，用于文化馆非遗展陈：
观众无需接触设备，用手势即可浏览非遗项目、播放介绍视频、查看 3D 展品与地图。

- 界面：PySide6（含 QtWebEngine 展示 3D / 地图）
- 识别：IPN-Hand 13 类手势，8 帧 RGB，CPU 实时推理
- 交互：手势驱动页面导航 + 视频快进快退 + 地图平移缩放 + 3D 模型旋转缩放

---

## 一、功能特性

### 页面
| 页面 | 内容 |
|---|---|
| 首页 | 6 项非遗卡片轮播、选中高亮、印章与墨韵背景 |
| 详情页·主视图 | 作品图**自动轮播**（3.5s，带页码）+ **项目信息卡**（类别/传承人/详实简介）+ 三个功能按钮 |
| 详情页·非遗详情 | 项目介绍（可滚动）+ **介绍视频**（循环播放、可手势快进快退）+ 3 张配图 + **项目二维码**（扫码了解）|
| 3D 交互展示 | three.js(r147) 加载 GLB 模型，自动居中/适配、自转，扁平模型自动侧倾 |
| 传承人风采 | 5 位传承人（视频/照片），上下切换；左/右可快进快退视频 |
| 非遗地图 | 高德瓦片地图，**地名常显**，手势平移 + 缩放 |
| 设置/手势说明 | 操作对照表 |

### 手势交互（按页面）
| 页面 | 手势 | 动作 |
|---|---|---|
| 首页 | 向左/向右抛出 | 上一项 / 下一项（到端点后进入地图 / 传承人）|
| 首页 | 单击 | 进入当前选中项目详情 |
| 详情页·主视图 | 向左/向右抛出 | 切换选中按钮（返回主页 / 非遗详情 / 交互展示）|
| 详情页·主视图 | 单击 | 确认（激活选中按钮）|
| 详情页·非遗详情 | 向左/向右抛出 | 视频**快退 / 快进 30 秒** |
| 详情页·非遗详情 | 单击 | 返回主视图 |
| 3D 展示 | 张开两次 / 缩小 / 双击 | 放大 / 缩小 / 旋转模型 |
| 3D 展示 | 单击 | 返回 |
| 传承人页 | 向左/向右抛出 | 视频快退 / 快进 30 秒 |
| 传承人页 | 向上/向下抛出 | 上一位 / 下一位传承人 |
| 传承人页 | 单击 | 返回 |
| 地图页 | 四个方向抛出 | 地图上/下/左/右平移 |
| 地图页 | 张开两次 / 缩小 | 地图放大 / 缩小 |
| 地图页 | 单击 | 返回 |

> 模型共 13 类，手势→动作的映射见 `src/core/gesture_mapper.py`
> （未绑定的类别：单指指向、双指指向、双指点击、双指双击、放大 —— 识别偏弱或易混，故意不绑动作）

### 防误触发机制（慢模型下保证体验）
- **显示与触发分离**：显示用即时结果（跟手），触发用平滑结果（稳定）
- **去抖**：连续 2 次相同动作才触发
- **冷却**：触发后 0.9s 内不响应新动作
- **锁存 + 松手复位**：同一动作触发后锁定，需"松手"（置信度掉下门槛）才能再次触发，杜绝举起不放连续翻页
- **最大锁存 2s**：超时自动解锁，避免卡死
- **"已执行"提示**：右上角短暂显示 `✔ 已执行：xx`

---

## 二、快速开始

### 环境
```bash
# 方式一：conda（推荐，本项目开发环境名为 gesture）
conda env create -f environment.yml && conda activate gesture

# 方式二：venv
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
```
> 运行依赖已含 Pillow（预处理用）。仅**素材处理脚本**额外需要 **Blender**（`fbx_to_glb.py` / `render_slides.py` 使用无头渲染）。

### 运行
```bash
python main.py
```

### 设备与资源要求
- **摄像头**：默认**自动选择**——有外接摄像头优先用外接，否则用笔记本自带（`config.CAMERA_AUTO_SELECT`）
- **权重**：`weights/TSQ_ipnhand_RGB_resnet50_shift0.50_blockres_avg_segment8_e50.pth`（**不在版本库中**，需另行放置，见第五节）
- **视频**：`assets/videos/**`（**不在版本库中**，见第四节）
- **3D 模型**：`assets/models/*.glb`（**不在版本库中**，可用脚本生成）

---

## 三、目录结构

```
dynamic_gesture_system/
├── main.py                     入口
├── src/
│   ├── config.py               全局配置（模型/推理/手势阈值/摄像头）
│   ├── core/
│   │   ├── camera.py           摄像头采集（自动选外接、CLAHE 仅用于预览）
│   │   ├── frame_buffer.py     线程安全帧缓冲
│   │   ├── inference.py        模型加载 + 推理线程（显示/触发双结果）
│   │   ├── gesture_mapper.py   13 类索引 → 控制动作映射
│   │   ├── project_data.py     读取 assets/projects.json
│   │   └── project_assets.py   素材路径解析（图片/模型/视频/二维码/轮播）
│   ├── model/                  DSTE-Net 网络定义（temporal_module 等）
│   └── ui/                     各页面（首页/详情/3D/传承人/地图/设置）
├── pages/                      viewer.html（3D）、map.html（地图）、three/leaflet
├── assets/
│   ├── projects.json           6 个非遗项目（名称/级别/类别/传承人/简介/介绍）
│   ├── inheritors.json         传承人页数据（姓名/项目/简介/视频/照片）
│   ├── gestures.json           13 类中文名（悬浮窗显示用）
│   ├── images/<slug>/          卡片图、详情图、传承人配图、二维码、轮播图
│   ├── models/<slug>.glb       3D 模型（脚本生成，未入库）
│   └── videos/                 介绍视频（未入库）
├── tools/
│   ├── prepare_assets.py       从 F:\非遗资料 生成图片素材（含裁剪/轮播图）
│   ├── fbx_to_glb.py           Blender 无头 FBX → GLB（归一化尺寸与中心）
│   └── render_slides.py        Blender 渲染 3D 模型 → 轮播图
├── weights/                    模型权重（未入库）
└── environment.yml / requirements.txt
```

---

## 四、素材与生成脚本

素材来自文化馆资料（本机 `F:\非遗资料`），已处理成 `assets/` 下的成品。

| 脚本 | 作用 |
|---|---|
| `python tools/prepare_assets.py` | 生成卡片图/详情图/传承人配图/二维码/轮播图（支持按图裁剪；F 盘不可用时用仓库内图片兜底）|
| `python tools/fbx_to_glb.py` | 把资料里的 FBX 转成 GLB：烘焙骨骼姿态、居中、统一缩放，供 3D 页加载 |
| `python tools/render_slides.py` | 用 Blender 把 GLB 渲染成轮播图（给缺高清照片的项目）|

**视频**：资料里的原始视频码率极高（3.9GB），需先转码为 720p/CRF28（约 20~60MB/个）后放入：
- 详情页视频 → `assets/videos/<slug>.mp4`
- 传承人页视频 → `assets/videos/inheritors/<文件名>.mp4`（文件名与 `inheritors.json` 中登记的一致）

**授权**：包公祠实景照来自 Wikimedia Commons（CC BY-SA 3.0），署名与许可要求见
`assets/images/CREDITS.md` —— **对外展示时需保留署名**，建议在设置页增加"图片来源"说明。

---

## 五、模型说明

- **网络**：ResNet-50 + DSTE 时空激励
  - LSTE：坐标注意力（`CoordAtt`）+ ECA 动态 3×3 卷积核（`fc1/fc2/bn2`）
  - GSTE：帧间差分 + 空间自注意力（`SpatialAttention`）
  - 时序帧数由权重固定为 **n_segment = 8**（`fc1` 输入维度即 8），**不可随意更改**
- **类别**：IPN-Hand **13 类**（B0A…G11），索引顺序已实机验证
- **权重**：`weights/TSQ_ipnhand_RGB_resnet50_shift0.50_blockres_avg_segment8_e50.pth`
  - 由服务器训练产出（含 `optimizer`，227MB；只提取 `state_dict` 可缩到 114MB，fp16 约 57MB）
  - 训练代码（改进版）：本地镜像 `F:\dste_dynamic_v4`，实际在服务器运行
  - 训练侧改进：水平翻转 + 方向类标签对调、类别均衡采样、ColorJitter/RandomErasing、
    `load_checkpoint` 兼容 torch≥2.6、`TemporalModule.count` 重置等
- **推理后端**：默认 **PyTorch（CPU）**；ONNX Runtime 代码保留但默认关闭
  （`config.USE_ONNX=False`：实测该模型含动态分组卷积，ORT 比 PyTorch 慢）
- **实测耗时**：CPU 单次推理约 0.5~0.7s（8 帧），页面切换体感延迟已通过"显示/触发分离 + 锁存"优化

---

## 六、调参速查（`src/config.py`）

| 参数 | 作用 | 当前值 |
|---|---|---|
| `NUM_SEGMENTS` | 送入模型的帧数（模型固定）| 8 |
| `SAMPLE_WINDOW_FRAMES` | 从最近多少帧里均匀抽帧（≈0.5s）| 15 |
| `SMOOTH_FRAMES` | 触发判定用最近几次结果平滑 | 2 |
| `CONSISTENCY_COUNT` | 连续几次相同才触发 | 2 |
| `CONFIDENCE_THRESHOLD` | 触发所需置信度 | 0.6 |
| `DISPLAY_CONFIDENCE` | 悬浮窗显示门槛（低于显示"无手势"）| 0.35 |
| `DISPLAY_HOLD_MS` / `DISPLAY_SWITCH_CONFIDENCE` | 显示保持时长 / 抢显示所需置信度 | 1000ms / 0.6 |
| `ACTION_COOLDOWN_MS` | 触发后冷却 | 900ms |
| `MAX_LOCK_MS` | 锁存最长时长（超时自动解锁）| 2000ms |
| `SEEK_STEP_MS` | 视频快进/快退步长 | 30000 |
| `CAMERA_AUTO_SELECT` | 自动优先外接摄像头 | True |
| `CAMERA_ENHANCE_PREVIEW` / `CAMERA_MIRROR_FEED` | 预览增强（仅显示）/ 喂模型是否镜像 | True / True |

> 识别偏慢/偏抖时：优先调 `CONFIDENCE_THRESHOLD`、`SMOOTH_FRAMES`、`ACTION_COOLDOWN_MS`。

---

## 七、打包（PyInstaller，暂未执行）

- 体积估算：运行时依赖约 1.0GB（PySide6 + torch + OpenCV）+ 素材（图片 5MB、模型 31MB、视频约 125MB）→ **约 1.3GB**
- 需一并打包：`pages/`（three.js、GLTFLoader、leaflet）、`assets/`、`weights/`
- 需收集：QtMultimedia 插件与 FFmpeg 后端 DLL（否则视频无法播放）、QtWebEngine 资源
- `assets/videos/`、`assets/models/`、`weights/` 均在 `.gitignore` 中，打包时需从本地目录取

---

## 八、参考

- DSTE-Net：Dynamic Spatial-Temporal Excitation Network（本系统采用的时空激励结构）
- TSM: Temporal Shift Module for Efficient Video Understanding — arXiv:1811.08383
- IPN Hand: A Video Dataset and Benchmark for Real-Time Continuous Hand Gesture Recognition —
  <https://github.com/GibranBenitez/IPN-hand>
- 素材与授权：见 `assets/images/CREDITS.md`
