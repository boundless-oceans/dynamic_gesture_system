# 测试

## 跑自动化测试

在仓库根目录：

```bash
python -m unittest discover -s tests -t .        # 全部
python -m unittest tests.test_gesture_gate -v    # 只跑某一个，看用例名
```

用标准库 `unittest`，**不需要额外装任何包**（pytest 也能直接收集这些用例）。
GUI 相关用例通过 `QT_QPA_PLATFORM=offscreen` 离屏运行，不需要显示器和摄像头。

## 有哪些

| 文件 | 覆盖内容 |
|---|---|
| `test_gesture_gate.py` | **去抖 / 锁存 / 冷却状态机**、松手解锁、触发门槛、六页手势路由、提示文案 |
| `test_frame_buffer.py` | 环形帧缓冲：窗口不足返回空、溢出丢最旧、push 拷贝、并发读写 |
| `test_gesture_mapper.py` | IPN-Hand 13 类索引顺序与控制手势映射（含"刻意不绑定"的类别） |
| `test_config_tuning.py` | 现场调参文件的载入/夹紧/坏文件容错/恢复默认 |
| `test_data_integrity.py` | 项目数与 slug 数一致、图片素材齐全、轮播顺序、传承人条目 |
| `test_pages_construct.py` | 七个页面 + 主窗口能否构造（离屏） |

`test_gesture_gate.py` 是最要紧的一个：那套状态机是调试最久、
也最容易被参数调整带坏的部分。它用桩对象直接调用真实的 `MainWindow._ocg`，
并用可控时钟断言冷却/锁存的时长，不依赖 `sleep`。

## 手工冒烟（要摄像头 / 显示器 / 人来判断）

```bash
python tests/manual/smoke_camera.py      # 摄像头 + 帧缓冲 + 预览悬浮窗
python tests/manual/smoke_inference.py   # 摄像头 + 推理，逐条打印识别结果
python tests/manual/smoke_app.py         # 完整应用，人工过一遍六个页面
```

`smoke_inference.py` 在调去抖/门槛参数时特别有用：它会同时打印平滑与即时两路结果。

## 手工诊断

```bash
python tests/check_weights.py            # 权重文件结构能否对上当前模型
```

## 已知的跳过项

`weights/`、`assets/models/`、`assets/videos/` 都在 `.gitignore` 里，
干净克隆中不存在，相关用例会自动 skip 而不是失败。本地有素材时才会真正执行。
