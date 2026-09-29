"""用 PyInstaller 打出可交付的**目录版**程序

    E:\\software\\miniconda3\\envs\\gesture\\python.exe tools/build_exe.py

**必须用 gesture 环境**跑，不是 base（base 里也有依赖，那是跑程序用的）。
产物与中间产物全落在 `F:\\非遗资料\\final_test\\`，仓库里不留 build/dist。

## 为什么是 onedir 而不是 onefile

  * **启动速度** —— onefile 每次启动都要把 1.2GB 解压到 `%TEMP%`，退出再删。
    做成开机自启的话，访客开机后会先面对十几秒黑屏。
  * **LGPL v3** —— PySide6 是 LGPL v3，要求使用者**能替换该库**。
    onefile 把它塞进单个 exe，做不到；onedir 下 Qt 是 `_internal/` 里独立的 DLL。

## 为什么 assets/ weights/ pages/ 不打进 bundle

这三样是"内容"不是"程序"，部署时铺在 exe 旁边。好处：

  * 换视频、换模型、改 HTML **不用重新打包**
    （README 里"视频到位后直接放入即可，无需改代码"靠的就是这个）
  * 现场的人自己能找到，不用钻进 `_internal/`

代码侧对应的就是 `src/paths.py`：打包后一切从 `app_dir()`（exe 所在）取，
而不是从 `__file__`（会指向只读的 `_internal/`）。
"""

import os
import shutil
import subprocess
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OUT_ROOT = r"F:\非遗资料\final_test"
APP_NAME = "庐州非遗手势展示"
ENTRY = os.path.join(REPO, "main.py")
ICON = os.path.join(REPO, "assets", "app_icon.ico")

# 铺在 exe 旁边的"内容"，不打进 bundle
CONTENT_DIRS = ["assets", "weights", "pages"]

# 环境里装了但运行期用不到的包。排除它们能砍体积，也少一堆无谓的 hook。
#
#   onnxruntime / onnx —— src/core/inference.py:57 那句 `import onnxruntime` 是包在
#       `if config.USE_ONNX` 里的，而 USE_ONNX = False，分支永不执行；
#       但 PyInstaller 是静态分析，会照样把它拉进来（连带 protobuf / flatbuffers /
#       ml_dtypes / coloredlogs / humanfriendly）。
#   tensorboardx —— 训练期的东西，运行期不用。
#
# ⚠ 不要动 jinja2 / fsspec / sympy / networkx / mpmath —— 那些是 **torch 自己的依赖**。
EXCLUDES = ["onnxruntime", "onnx", "tensorboardx", "tensorflow"]


def _rm(path: str) -> None:
    if os.path.isdir(path):
        shutil.rmtree(path, ignore_errors=True)
    elif os.path.exists(path):
        os.remove(path)


def build(console: bool = False, skip_content: bool = False,
          refresh_content: bool = False) -> str:
    dist = os.path.join(OUT_ROOT, "dist")
    work = os.path.join(OUT_ROOT, "build")
    specdir = os.path.join(OUT_ROOT, "spec")

    if not os.path.exists(ICON):
        sys.exit("图标不存在：%s\n先跑 python tools/make_icon.py" % ICON)

    # 只清 PyInstaller 自己的产物（_internal/ 与 exe），**保留内容目录** ——
    # 否则每次重建都要重拷 500MB 的 assets/weights。
    # 之所以要清：增量构建有时会留下上一次的 DLL，打出来的包"看着是新的、
    # 其实混着旧的"，这种最难查。
    app_dir = os.path.join(dist, APP_NAME)
    _rm(os.path.join(app_dir, "_internal"))
    _rm(os.path.join(app_dir, APP_NAME + ".exe"))
    _rm(work)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", APP_NAME,
        "--icon", ICON,
        "--distpath", dist,
        "--workpath", work,
        "--specpath", specdir,
    ]
    for m in EXCLUDES:
        cmd += ["--exclude-module", m]
    if not console:
        cmd.append("--windowed")
    cmd.append(ENTRY)

    print("[build] %s" % " ".join('"%s"' % c if " " in c else c for c in cmd))
    t0 = time.time()
    r = subprocess.run(cmd, cwd=REPO)
    if r.returncode != 0:
        sys.exit("[build] PyInstaller 失败，返回码 %d" % r.returncode)
    print("[build] 完成，用时 %.1f 分钟" % ((time.time() - t0) / 60))

    app_dir = os.path.join(dist, APP_NAME)
    print("[build] 产物目录：%s" % app_dir)
    if skip_content:
        print("[build] --skip-content：跳过拷贝内容目录")
    else:
        copy_content(app_dir, force=refresh_content)
    return app_dir


def copy_content(app_dir: str, force: bool = False) -> None:
    """把 assets/ weights/ pages/ 铺到 exe 旁边（约 500MB）

    已经拷过就跳过 —— 内容目录很少变，而每轮重建都重拷 500MB 会拖慢迭代。
    真要刷新加 `--refresh-content`。
    """
    print("[content] 拷贝内容目录（约 500MB，第一次要一会儿）")
    t0 = time.time()
    for name in CONTENT_DIRS:
        src = os.path.join(REPO, name)
        dst = os.path.join(app_dir, name)
        if not os.path.isdir(src):
            print("  ✗ %s 不存在，跳过" % name)
            continue
        if not force and os.path.isdir(dst) and os.listdir(dst):
            print("  = %s 已存在，跳过（--refresh-content 可强制重拷）" % name)
            continue
        shutil.copytree(src, dst, dirs_exist_ok=True)
        print("  ✓ %s" % name)
    print("[content] 完成，用时 %.1f 秒" % (time.time() - t0))


if __name__ == "__main__":
    build(console="--console" in sys.argv,
          skip_content="--skip-content" in sys.argv,
          refresh_content="--refresh-content" in sys.argv)
