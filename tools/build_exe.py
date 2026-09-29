"""用 PyInstaller 打出可交付的**目录版**程序

    python tools/build_exe.py

**必须用 `gesture` 那个 conda 环境跑**，不是平时运行程序用的环境
（先 `conda activate gesture`，或用该环境 `python.exe` 的全路径执行）。

产物与中间产物都落在下面 `OUT_ROOT` 指向的目录，**仓库里不留** build/dist。
`OUT_ROOT` 是本机约定（交付时把那个目录整个拷走），换机器按需改这一行即可。

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

# 构建产物落在这里。**这是本机约定**（交付时把 OUT_ROOT/<APP_NAME> 整个拷走），
# 换一台机器打包就改这一行 —— 其余代码都不依赖具体位置。
OUT_ROOT = r"F:\非遗资料\final_test"
APP_NAME = "庐州非遗手势展示"
ENTRY = os.path.join(REPO, "main.py")
ICON = os.path.join(REPO, "assets", "app_icon.ico")

# 铺在 exe 旁边的"内容"，不打进 bundle
CONTENT_DIRS = ["assets", "weights", "pages"]

# 首次安装脚本（只建桌面快捷方式，**不做开机自启**）。源码在版本库里，构建时拷到 exe 旁边，
# 操作员解压后双击「首次安装.bat」即可。两个文件都刻意只用 ASCII —— 见其文件头。
INSTALLER_DIR = os.path.join(REPO, "tools", "installer")

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
    # 交付目录**直接**落在 OUT_ROOT 下（不再套一层 dist/），这样交付时一眼能看到；
    # 中间产物用下划线前缀区分，别和交付物混在一起。
    dist = OUT_ROOT
    work = os.path.join(OUT_ROOT, "_build")
    specdir = os.path.join(OUT_ROOT, "_spec")

    if not os.path.exists(ICON):
        sys.exit("图标不存在：%s\n先跑 python tools/make_icon.py" % ICON)

    # 整个产物目录删掉重来 —— 交付物必须是"从零生成"的，不能混进上次的残留
    # （调试时的 stdout 文件、logs/、旧 exe……）。
    # 代价是每次重建都要重拷 assets/weights，但实测只有 **6.3 秒**，
    # 不值得为省这点时间留下"看着是新的、其实混着旧的"的风险。
    app_dir = os.path.join(dist, APP_NAME)
    print("[build] 清掉旧产物目录：%s" % app_dir)
    _rm(app_dir)
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
    copy_installer(app_dir)
    return app_dir


def copy_installer(app_dir: str) -> None:
    """把首次安装脚本拷到 exe 旁边（操作员解压后双击那个 .bat）

    文本文件**统一转成 CRLF**：交付物是 Windows 上的东西，该用 Windows 的换行惯例。
    这件事放在这里做，而不是指望仓库里恰好是什么 —— git 的 autocrlf 会按检出时的
    设置改变工作区的换行，靠它不可靠。（BOM 原样保留：`setup.ps1` 与 `使用说明.txt`
    靠它才能被 PowerShell 5.1 / 记事本正确读出中文。）
    """
    if not os.path.isdir(INSTALLER_DIR):
        print("[installer] ✗ 找不到 %s，跳过" % INSTALLER_DIR)
        return
    for name in sorted(os.listdir(INSTALLER_DIR)):
        src = os.path.join(INSTALLER_DIR, name)
        if not os.path.isfile(src):
            continue
        dst = os.path.join(app_dir, name)
        if name.lower().endswith((".bat", ".cmd", ".ps1", ".txt")):
            with open(src, "rb") as f:
                raw = f.read()
            # 先归一成 LF 再统一变 CRLF，避免把已有的 CRLF 变成 CRCRLF
            raw = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            with open(dst, "wb") as f:
                f.write(raw)
        else:
            shutil.copy2(src, dst)
        print("  ✓ %s" % name)


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
