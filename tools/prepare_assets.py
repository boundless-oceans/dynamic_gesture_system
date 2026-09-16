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
QR_DIR = r"F:\非遗资料\文化馆一期资料\h5二维码\十个二维码"

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
            # 原来用"包公吃鱼"是黑白线稿，换成彩色连环画
            os.path.join(C, "BGGSImages", "包公断子.jpg"),
        ],
    },
    "luju": {
        "thumb": os.path.join(U, "Res", "ModelImg", "4庐剧.png"),
        # 这三张是视频截图：带"好看视频"水印(右上)与字幕(底部)，需裁剪
        "details": [
            {"src": os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "梁祝.png"),
             "crop": (0.0, 0.0, 1.0, 0.73)},                       # 只剩底部字幕
            {"src": os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "小姑.png"),
             "crop": (0.0, 0.13, 0.85, 0.80)},                     # 去右上水印(含图标)+底部字幕
            {"src": os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "双缩骨.png"),
             "crop": (0.0, 0.20, 0.85, 0.80)},
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
        # 卡片图用一幅铁字书法作品（原来是"铁研居室内"全景，主体不突出）
        "thumb": os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山",
                              "抗疫作品 (2)铁字书法《治疫救人  最美医护》.jpg"),
        "details": [
            os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山", "铁字书法《宁静致远》.jpg"),
            os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山", "铁字书法《水北原南野草新》.jpg"),
            os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山", "铁字书法《望庐山瀑布》 (1).jpg"),
        ],
    },
}


# 传承人页专用配图：来源与卡片图(thumb)不同，避免和首页按钮图重复
# crop 为相对比例 (left, top, right, bottom)，用于裁掉水印/字幕
# fallback: 原始素材(F盘)不可用时的兜底——改用仓库内的详情图 n.jpg
PORTRAITS = {
    "hulu": {"src": os.path.join(M2, "葫芦烙画", "IMG_20200306_115458.jpg"),
             "fallback": {"idx": 2}},
    "liumingchuan": {"src": os.path.join(C, "Bottom", "刘铭传潜山埋忠骨.jpg"),
                     "fallback": {"idx": 3}},
    "baogong": {"src": os.path.join(C, "BGGSImages", "以民为贵开仓放粮.jpg"),
                "fallback": {"idx": 3}},
    "luju": {"src": os.path.join(U, "Res", "Img_Xiangqing", "luju", "luju", "梁祝.png"),
             "crop": (0.0, 0.0, 1.0, 0.72),          # 裁掉底部字幕
             "fallback": {"idx": 1, "crop": (0.0, 0.0, 1.0, 0.72)}},
    "huobihua": {"src": os.path.join(MAT, "文化馆项目资料整理", "火笔画", "火笔画申报书配套照片", "02.jpg"),
                 "fallback": {"idx": 2}},
    # 传承人页是"人"：用传承人工作照更贴切
    "wushantiezi": {"src": os.path.join(M2, "吴山铁字", "省级项目 吴山铁字 省级传承人 郑书山",
                                        "郑书山工作照a (1).JPG"),
                    "fallback": {"idx": 2}},
}


# 项目二维码（扫一扫了解详情）；火笔画、吴山铁字暂无对应二维码
QRS = {
    "hulu": "葫芦雕刻.png",
    "liumingchuan": "刘铭传故事.png",
    "baogong": "包公故事.png",
    "luju": "庐剧.png",
}


def copy_qrs():
    """把二维码原样拷到 assets/images/<slug>/qr.png"""
    print("\n[二维码]")
    for slug, fn in QRS.items():
        src = os.path.join(QR_DIR, fn)
        if not os.path.exists(src):
            print(f"  ✗ {slug}: 源缺失 {src}")
            continue
        dst = os.path.join(OUT_ROOT, slug, "qr.png")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with Image.open(src) as im:
            im.save(dst, "PNG")          # 保持清晰，不缩放
        print(f"  ✓ {slug}/qr.png  {im.size}  <- {fn}")


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


def convert(src: str, dst: str, long_side: int, crop=None):
    im = _load_rgb(src)
    if crop:
        w, h = im.size
        l, t, r, b = crop
        im = im.crop((int(w * l), int(h * t), int(w * r), int(h * b)))
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
        for i, item in enumerate(spec["details"], 1):
            # 详情项可以是路径字符串，也可以是 {"src":..., "crop":(...)}
            s = item["src"] if isinstance(item, dict) else item
            crop = item.get("crop") if isinstance(item, dict) else None
            if not os.path.exists(s):
                print(f"  ✗ detail{i} 源缺失: {s}"); missing.append((slug, f"detail{i}", s)); continue
            size, n = convert(s, os.path.join(out_dir, f"{i}.jpg"), DETAIL, crop)
            print(f"  ✓ {i}.jpg {size} {n//1024}KB  <- {os.path.basename(s)}{' (裁剪)' if crop else ''}")
        pspec = PORTRAITS.get(slug)
        if pspec:
            ps, crop = pspec["src"], pspec.get("crop")
            note = ""
            if not os.path.exists(ps):
                # 兜底：原始素材不可用时，用仓库内已生成的详情图
                fb = pspec.get("fallback")
                local = os.path.join(out_dir, f"{fb['idx']}.jpg") if fb else ""
                if local and os.path.exists(local):
                    ps, crop = local, fb.get("crop")
                    note = "（兜底：用仓库内详情图）"
                else:
                    print(f"  ✗ portrait 源缺失且无兜底: {ps}")
                    missing.append((slug, "portrait", ps)); ps = None
            if ps:
                size, n = convert(ps, os.path.join(out_dir, "portrait.jpg"), THUMB, crop)
                print(f"  ✓ portrait.jpg {size} {n//1024}KB  <- {os.path.basename(ps)}{note}")
    copy_qrs()
    print("\n== 缺失/待补 ==" if missing else "\n== 全部完成 ==")
    for m in missing:
        print("  ", m)


if __name__ == "__main__":
    main()
