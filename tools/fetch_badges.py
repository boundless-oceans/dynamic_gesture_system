"""把 README 顶部的徽章下载到本地 docs/badges/

README 里用**相对路径**引用这些文件，而不是直接写 shields.io 的 URL：

  * 编辑器预览（VS Code 内置预览 / Markdown Preview Enhanced）对远程内容
    有安全限制时，远程图片会加载不出来；本地文件不受影响
  * 断网、或 shields.io 被网络策略挡住时照样能显示
  * 不依赖第三方服务在展示时的可用性

代价是徽章不会自动更新——改了版本号之后重新跑一次即可：

    python tools/fetch_badges.py

只依赖标准库，不需要装任何东西。
"""
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "docs", "badges")

# 文件名 → (label, message, color, logo)
# 增删徽章时改这里，然后同步 README 顶部的引用
BADGES = {
    "python.svg":   ("Python",   "3.10",                   "3776AB", "python"),
    "pyside6.svg":  ("PySide6",  "6.11",                   "41CD52", "qt"),
    "pytorch.svg":  ("PyTorch",  "2.13 CPU",               "EE4C2C", "pytorch"),
    "opencv.svg":   ("OpenCV",   "5.0",                    "5C3EE8", "opencv"),
    "platform.svg": ("Platform", "Windows",                "0078D6", "windows"),
    "model.svg":    ("DSTE-Net", "IPN-Hand 13 classes",     "8957e5", None),
    "tests.svg":    ("tests",    "104 passed",             "4CAF50", None),
    "license.svg":  ("License",  "MIT",                    "3DA639", "opensourceinitiative"),
}


def _url(label: str, message: str, color: str, logo: str) -> str:
    """静态徽章 URL。shields 的转义规则：短横线写两遍、空格写 %20、下划线写两遍。"""
    esc = lambda s: s.replace("-", "--").replace("_", "__").replace(" ", "%20")
    url = "https://img.shields.io/badge/%s-%s-%s" % (esc(label), esc(message), color)
    if logo:
        url += "?logo=%s&logoColor=white" % logo
    return url


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "fetch_badges.py"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = []
    for name, (label, message, color, logo) in BADGES.items():
        url = _url(label, message, color, logo)
        dst = os.path.join(OUT_DIR, name)
        try:
            data = fetch(url)
        except Exception as e:                       # noqa: BLE001
            print(f"  x {name:<14} 下载失败: {e}")
            failed.append(name)
            continue
        # 确认拿到的是 SVG 而不是错误页——写坏了比缺文件更难查
        head = data[:200].lstrip()
        if not head.startswith(b"<svg") and b"<svg" not in head:
            print(f"  x {name:<14} 返回的不是 SVG（{len(data)} 字节），已保留原文件")
            failed.append(name)
            continue
        with open(dst, "wb") as f:
            f.write(data)
        print(f"  + {name:<14} {len(data):>5} 字节   <- {label}: {message}")

    print(f"\n输出目录: {OUT_DIR}")
    if failed:
        print("失败:", ", ".join(failed))
        return 1
    print("全部完成。README 顶部用相对路径引用即可，例如：")
    print("    ![Python](docs/badges/python.svg)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
