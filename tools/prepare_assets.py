"""把 F:\\非遗资料 里的原始素材处理成应用可用图片。

产出（每个项目一个目录）：
    assets/images/<slug>/thumb.jpg     卡片图（长边 500）
    assets/images/<slug>/1..3.jpg      详情图（长边 1200）

源素材路径是本机 F 盘资料，仅用于一次性处理；处理后应用只依赖 assets/ 下的成品。
"""
import os
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(REPO, "assets", "images")

# 素材来源（本机）
MAT = r"F:\非遗资料"
U = os.path.join(MAT, r"_extracted\yuanma\LuZhouFeiYi_2019.4.30\Assets")
C = os.path.join(MAT, r"_extracted\WHG\WHG\assets\Images")
M2 = os.path.join(MAT, "文化馆二期")

THUMB = 500
DETAIL = 1200

# slug -> {"thumb": 源, "details": [源...]}
MAPPING = {
    "hulu": {
        "thumb": os.path.join(M2, "葫芦烙画", "IMG_20200520_105514.jpg"),
        "details": [
            os.path.join(M2, "葫芦烙画", "IMG_20200520_105514.jpg"),
            os.path.join(M2, "葫芦烙画", "IMG_20200520_105532.jpg"),
            os.path.join(M2, "葫芦烙画", "IMG_20191212_154037.jpg"),
        ],
    },
    "liumingchuan": {
        "thumb": os.path.join(U, "Res", "ModelImg", "2刘铭传.png"),
        "details": [
            os.path.join(C, "Bottom", "刘铭传.jpg"),
            os.path.join(C, "Bottom", "刘铭传旧居.jpg"),
            os.path.join(C, "Bottom", "刘铭传墓园.jpg"),
        ],
    },
    "baogong": {
        "thumb": os.path.join(U, "Res", "ModelImg", "1包公.png"),
        "details": [
            os.path.join(C, "BGGSImages", "包公不持一砚归.jpg"),
            os.path.join(C, "BGGSImages", "包公审石头.jpg"),
            os.path.join(C, "BGGSImages", "包公吃鱼.png"),
        ],
    },
    "luju": {
        "thumb": os.path.join(U, "Res", "ModelImg", "4庐剧.png"),
        "details": [
            os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "梁祝.png"),
            os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "小姑.png"),
            os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "双缩骨.png"),
        ],
    },
    "huobihua": {
        "thumb": os.path.join(U, "Res", "ModelImg", "9火笔画.png"),
        "details": [
            os.path.join(MAT, "文化馆项目资料整理", "火笔画", "火笔画申报书配套照片", f"{n:02d}.jpg")
            for n in (1, 3, 5)
        ],
    },
    "wushantiezi": {
        # 无现成卡片图，用"代表作陈列"实拍；风格与其它卡片不一致（待改）
        "thumb": os.path.join(M2, "吴山铁字", "吴山铁字照片 邓之元",
                              "邓华丽  2020年于吴山铁研居拍摄。图为铁硏居室内，展览省级非遗传承人邓之元部分代表作.jpg"),
        "details": [
            os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山", "铁字书法《宁静致远》.jpg"),
            os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山", "铁字书法《水北原南野草新》.jpg"),
            os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山", "铁字书法《望庐山瀑布》 (1).jpg"),
        ],
    },
}


def _load_rgb(src: str) -> Image.Image:
    im = Image.open(src)
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    return im


def convert(src: str, dst: str, long_side: int):
    im = _load_rgb(src)
    im.thumbnail((long_side, long_side), Image.LANCZOS)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    im.save(dst, "JPEG", quality=88, optimize=True)
    return im.size, os.path.getsize(dst)


def main():
    missing = []
    for slug, spec in MAPPING.items():
        out_dir = os.path.join(OUT_ROOT, slug)
        print(f"\n[{slug}]")
        src = spec["thumb"]
        if not os.path.exists(src):
            print(f"  ✗ thumb 源缺失: {src}"); missing.append((slug, "thumb", src))
        else:
            size, n = convert(src, os.path.join(out_dir, "thumb.jpg"), THUMB)
            print(f"  ✓ thumb.jpg {size} {n//1024}KB  <- {os.path.basename(src)}")
        for i, s in enumerate(spec["details"], 1):
            if not os.path.exists(s):
                print(f"  ✗ detail{i} 源缺失: {s}"); missing.append((slug, f"detail{i}", s)); continue
            size, n = convert(s, os.path.join(out_dir, f"{i}.jpg"), DETAIL)
            print(f"  ✓ {i}.jpg {size} {n//1024}KB  <- {os.path.basename(s)}")
    print("\n== 缺失/待补 ==" if missing else "\n== 全部完成 ==")
    for m in missing:
        print("  ", m)


if __name__ == "__main__":
    main()
