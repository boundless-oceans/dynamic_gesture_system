"""运行期路径：说清"程序在哪"和"数据写哪"

**为什么需要单独一个模块**

开发时和打包后，`__file__` 的含义完全不同：

  * **开发时** —— `__file__` 就在仓库里，一切从它往上推算就行
  * **打包后**（PyInstaller）—— `__file__` 指向 `_internal/`，那是 **bundle 内部**，
    只读。而内容文件（`assets/` `weights/` `pages/`）**并不在 bundle 里**：
    它们是部署时铺在 exe 旁边的，这样换素材、换模型不用重新打包

所以必须显式区分两个目录：

    app_dir()   程序目录 —— exe 所在，内容文件也在这儿
    data_dir()  可写目录 —— `logs/` 与 `config_local.json` 写这儿

**开发时两者都等于仓库根**，因此开发与现有测试的行为完全不变
（`sys.frozen` 是 PyInstaller 注入的，本地跑永远是 False）。

反过来说，这个模块的存在就是"打包后不再有 `__file__` 可用"这件事的唯一答案 ——
以后新增任何路径常量，都从这里取，别再自己 `__file__` 往上推算。
"""

import os
import sys

# src/paths.py → src/ → 仓库根
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_frozen() -> bool:
    """是否运行在 PyInstaller 打出来的包里"""
    return bool(getattr(sys, "frozen", False))


def app_dir() -> str:
    """程序目录：exe 所在，`assets/` `weights/` `pages/` 也铺在这儿（只读资源）"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return _REPO_ROOT


def data_dir() -> str:
    """可写目录：`logs/` 与 `config_local.json` 写这儿。

    目标部署方式是 zip 解压到普通目录（D 盘），程序目录一定可写，所以**不做**
    "写不进去就退到 `%LOCALAPPDATA%`"的退化 —— 那会让"日志到底在哪"变成一件
    要看情况的事，现场排障时反而更麻烦。

    真遇到只读目录（有人把程序塞进 `Program Files`），由 `check_writable()`
    在启动时**明确报出来**，而不是悄悄写不进去。
    """
    return app_dir()


def resource_path(*parts: str) -> str:
    """内容文件的完整路径，例如 `resource_path("assets", "gestures.json")`"""
    return os.path.join(app_dir(), *parts)


def check_writable() -> str | None:
    """探测数据目录是否真的可写。正常返回 None，否则返回一段给人看的说明。

    **为什么要显式探测**：写不进去的后果是"日志一条没有、现场调参存不下来"，
    而这两件事都不会报错 —— 典型的静默失效。更麻烦的是，那种情况下日志本身
    也建不出来，**弹窗是唯一的告知途径**。
    """
    target = data_dir()
    probe = os.path.join(target, ".write_probe")
    try:
        os.makedirs(target, exist_ok=True)
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
    except Exception as e:
        return ("数据目录不可写：\n%s\n\n%s\n\n"
                "日志与「保存为默认」的现场调参都无法保存。\n"
                "请把程序移到可写位置（例如 D 盘）后重新启动。" % (target, e))
    return None
