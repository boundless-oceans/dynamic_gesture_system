"""生成应用图标 assets/app_icon.ico

产物用于三处，做**一个** `.ico` 就够了：
  * exe 的图标（PyInstaller `--icon`）
  * 桌面/开始菜单快捷方式 —— `.lnk` 默认沿用目标 exe 的图标，不用单独设
  * 任务栏与窗口图标（`QApplication.setWindowIcon`）

**按尺寸分别绘制**，而不是画一张 256 再缩到底：

  | 尺寸      | 字体   | 文字   | 为什么 |
  |----------|--------|--------|--------|
  | >= 32px  | 楷体   | 庐州   | 有韵味；这个尺寸下两个字看得清 |
  | 24/16px  | 黑体   | 庐     | 16px 放两个字每字只有约 6px，糊成一团；<br>楷体笔画粗细不均，小尺寸下细笔画会直接消失 |

配色取自 `src/ui/splash.py` 的启动画面渐变（白→天蓝→深藏青），
但整体压深了一档：图标要落在各种壁纸和任务栏上，浅色底配浅色字会糊。
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFont

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ICO = os.path.join(REPO, "assets", "app_icon.ico")

FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
FONT_KAI = os.path.join(FONT_DIR, "STKAITI.TTF")     # 华文楷体，应用界面一直在用
FONT_HEI = os.path.join(FONT_DIR, "simhei.ttf")      # 黑体，小尺寸用

# 渐变：顶部取启动画面渐变的收尾色，底部取启动画面标题用的深藏青
GRAD_TOP = (91, 167, 209)        # #5BA7D1
GRAD_BOTTOM = (26, 58, 92)       # #1a3a5c
TEXT_COLOR = (255, 255, 255)
CORNER_RATIO = 0.22              # 圆角半径占边长的比例

SIZES = [256, 128, 64, 48, 32, 24, 16]
# 这个尺寸及以上才用"楷体 + 两个字"。实测 32px 放两个字已经糊了，
# 而同期换成"黑体 + 单字"反而清楚 —— 所以分界线定在 48。
BIG_CUTOFF = 48

SS = 4                           # 先在 4 倍画布上画，再缩下来 —— 圆角和字边都更顺


def _gradient(size: int) -> Image.Image:
    """竖直线性渐变。先画一列像素再横向拉满，比逐像素快得多。"""
    strip = Image.new("RGB", (1, size))
    px = strip.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(round(GRAD_TOP[i] + (GRAD_BOTTOM[i] - GRAD_TOP[i]) * t)
                         for i in range(3))
    return strip.resize((size, size), Image.NEAREST)


def _rounded_mask(size: int, radius: int) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size - 1, size - 1],
                                        radius=radius, fill=255)
    return m


def _render(size: int) -> Image.Image:
    s = size * SS
    canvas = _gradient(s)
    draw = ImageDraw.Draw(canvas)

    if size >= BIG_CUTOFF:
        text, font_file, ratio = "庐州", FONT_KAI, 0.34
    else:
        text, font_file, ratio = "庐", FONT_HEI, 0.52

    font = ImageFont.truetype(font_file, int(s * ratio))
    # 用 textbbox 量真实外框再居中：不同字体的基线留白不一样，
    # 直接按字号居中会偏上/偏下
    box = draw.textbbox((0, 0), text, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.text(((s - w) / 2 - box[0], (s - h) / 2 - box[1]),
              text, font=font, fill=TEXT_COLOR)

    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    icon.paste(canvas, (0, 0), _rounded_mask(s, int(s * CORNER_RATIO)))
    return icon.resize((size, size), Image.LANCZOS)


def build_ico() -> str:
    frames = [_render(n) for n in SIZES]
    os.makedirs(os.path.dirname(OUT_ICO), exist_ok=True)
    frames[0].save(OUT_ICO, format="ICO",
                   sizes=[(n, n) for n in SIZES], append_images=frames[1:])
    return OUT_ICO


def build_preview(path: str) -> str:
    """出一张对照图，分两行 —— 一行看实际尺寸，一行把小尺寸放大看糊到什么程度。

    两行是必须的：放大区如果和实际尺寸排在同一行，会盖住右边那几档小图标。
    """
    frames = {n: _render(n) for n in SIZES}
    pad, gap = 20, 18
    ZOOM, ZOOMED = 8, (48, 32, 24, 16)  # 放大倍数 / 要放大看的几档

    small = ImageFont.truetype(FONT_HEI, 13)
    big_font = ImageFont.truetype(FONT_HEI, 14)

    row1_w = pad * 2 + sum(frames[n].width for n in SIZES) + gap * (len(SIZES) - 1)
    row1_h = max(frames[n].height for n in SIZES)
    row2_items = [(n, frames[n].resize((n * ZOOM, n * ZOOM), Image.NEAREST))
                  for n in ZOOMED]
    row2_w = pad * 2 + sum(z.width + 90 for _, z in row2_items)
    row2_h = max(z.height for _, z in row2_items)

    W = max(row1_w, row2_w)
    H = 30 + row1_h + 26 + 30 + row2_h + 26
    sheet = Image.new("RGB", (W, H), (246, 246, 246))
    d = ImageDraw.Draw(sheet)

    # ---- 第一行：实际尺寸，底边对齐 ----
    d.text((pad, 10), "① 实际尺寸（底边对齐，图中即屏幕上真实像素）",
           font=big_font, fill=(30, 30, 30))
    base = 30 + row1_h
    x = pad
    for n in SIZES:
        f = frames[n]
        y = base - f.height
        sheet.paste(f, (x, y), f)
        d.text((x, y + f.height + 5), f"{n}px", font=small, fill=(60, 60, 60))
        x += f.width + gap

    # ---- 第二行：小尺寸放大 ----
    y2 = base + 26 + 30
    d.text((pad, base + 26), f"② 小尺寸放大 {ZOOM} 倍（看清糊到什么程度）",
           font=big_font, fill=(30, 30, 30))
    x = pad
    for n, z in row2_items:
        sheet.paste(z, (x, y2))
        note = "楷体·庐州" if n >= BIG_CUTOFF else "黑体·庐"
        d.text((x, y2 + z.height + 5), f"{n}px → {note}", font=small, fill=(60, 60, 60))
        x += z.width + 90

    sheet.save(path, "PNG")
    return path


if __name__ == "__main__":
    ico = build_ico()
    print(f"✓ {os.path.relpath(ico, REPO)}  "
          f"{os.path.getsize(ico)//1024}KB  含 {len(SIZES)} 个尺寸: {SIZES}")
    prev = os.path.join(REPO, "_tmp_icon_preview.png")
    build_preview(prev)
    print(f"✓ 预览图 {os.path.relpath(prev, REPO)}")
