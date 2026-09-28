"""把文化馆提供的原始素材处理成应用可用图片。

产出（每个项目一个目录）：
    assets/images/<slug>/thumb.jpg     卡片图（长边 500）
    assets/images/<slug>/1..3.jpg      详情图（长边 1200）

源素材路径是本机 F 盘资料，仅用于一次性处理；处理后应用只依赖 assets/ 下的成品。
"""
import os
import sys
# Windows 控制台默认是 GBK，直接打印 ✓/✗ 会抛 UnicodeEncodeError 让脚本中途崩掉
# （实测：生成到一半崩了，产物只写了一半）。强制 UTF-8 输出，任何终端都能跑完。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ROOT = os.path.join(REPO, "assets", "images")
QR_DIR = r"F:\非遗资料\文化馆一期资料\h5二维码\十个二维码"

# 素材来源（本机）
MAT = r"F:\非遗资料"
U = os.path.join(MAT, r"_extracted\yuanma\LuZhouFeiYi_2019.4.30\Assets")
C = os.path.join(MAT, r"_extracted\WHG\WHG\assets\Images")
M2 = os.path.join(MAT, "文化馆二期")
LJ = os.path.join(MAT, "文化馆项目资料整理", "庐剧")
LM = os.path.join(MAT, "文化馆项目资料整理", "刘铭传故事")
LM_GJ = os.path.join(LM, "1 刘铭传故居")

THUMB = 500
DETAIL = 1200


def find_src(directory: str, *keywords: str) -> str:
    """按关键词在目录里定位素材源文件。

    **为什么不直接写文件名**：素材盘上这几个文件名里带着摄影者的手机号
    （形如 `…李德荣摄   137xx…jpg`）。代码会进公开仓库，第三方的个人信息
    不该跟着进去，所以改成按关键词匹配。关键词都挑的是**与手机号无关**的部分，
    将来文件名里的手机号被去掉，匹配照样成立。

    这是生成脚本，只在插着素材盘的机器上跑，所以：

      - 目录不存在 / 找不到文件 / 匹配不唯一 —— 一律返回一个不存在的路径，
        交给各调用点已有的"源缺失"分支统一报告
      - **不在这里抛异常**：MAPPING / SLIDES 是模块级构造的，
        抛异常会让脚本连启动都做不到
      - 但"匹配不唯一"是关键词挑宽了（代码问题，不是素材缺失），额外打印出来
    """
    if not os.path.isdir(directory):
        return os.path.join(directory, "【目录不存在】" + "_".join(keywords))
    hits = [f for f in os.listdir(directory) if all(k in f for k in keywords)]
    if len(hits) == 1:
        return os.path.join(directory, hits[0])
    print(f"  ✗ 源定位失败（匹配到 {len(hits)} 个）: {os.path.basename(directory)}"
          f"  关键词={list(keywords)}")
    for h in hits:
        print(f"      {h}")
    return os.path.join(directory, "【定位失败】" + "_".join(keywords))

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
        # 详情页右列只显示 2 张（第 3 格是二维码），选中景 + 墓园
        # 注意：680811...jpg 与"宫保第2"其实是同一个红门内景的重复拍摄，
        # 只用其中一张 —— 之前两张分散在详情页和轮播里，看着像重复。
        "details": [
            os.path.join(LM, "680811d938913148a5346d661938083.jpg"),          # 宫保第红门内景
            find_src(LM_GJ, "潜山埋忠骨"),                                     # 刘铭传墓园
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
        # 原来是视频截图（带"好看视频"水印和字幕，只能靠裁剪规避，抠出来的
        # 画面又糊又碎）。改用文化馆项目资料里的舞台剧照，画质和构图都好得多。
        "details": [
            os.path.join(LJ, "安徽省倒七戏剧团梁祝.png"),
            os.path.join(LJ, "安徽庐剧团改编的双锁柜.png"),
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
    # 刘铭传没有介绍视频，非遗详情页中列会用这张充位 —— 放人物画像最贴题。
    # 中列是竖长的，画像 1464x2292 正好；先前用过墓园、故居，全都是风景，缺"人"。
    "liumingchuan": {"src": os.path.join(LM_GJ, "刘铭传.png"),
                     "fallback": {"idx": 2}},
    "baogong": {"src": os.path.join(C, "BGGSImages", "以民为贵开仓放粮.jpg"),
                "fallback": {"idx": 3}},
    # 庐剧没有介绍视频，非遗详情页中列会用这张充位，所以挑最出彩的一张
    # （原先是裁剪过的视频截图，又扁又糊）
    "luju": {"src": os.path.join(LJ, "《孔雀东南飞之焦仲卿妻》.png"),
             "fallback": {"idx": 1}},
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


# 详情页主视图的"作品轮播图"：使用与详情页(1~3.jpg)不重复的其他照片
# 生成 assets/images/<slug>/slide1.jpg, slide2.jpg ...
SLIDES = {
    "hulu": [
        # 传承人郑小良绘制葫芦的工作照（比纯摆件照有变化）
        os.path.join(M2, "葫芦烙画", "mmexport1572247988256.jpg"),
        os.path.join(M2, "葫芦烙画", "IMG_20200520_105609.jpg"),
    ],
    # 轮播与详情页各用各的：梁祝、双锁柜已给详情页，这里用其余舞台剧照
    # （《汪鸿云和武克英主演的红楼梦》是白底抠图 + 人名标注，混在舞台照里不协调，不用）
    "luju": [
        os.path.join(LJ, "2016年元旦戏曲晚会《秦雪梅观画》.png"),
        os.path.join(LJ, "周总理接见庐剧演员.png"),
        os.path.join(LJ, "半把剪刀.png"),
        os.path.join(LJ, "大型现代戏《村长娘子》.png"),
    ],
    # 轮播与详情页各用各的，且彼此不重样：荷塘全景 / 故居航拍 / 人物照。
    # 画像挪去详情页中列充位了；这里换成 Wikimedia Commons 的公有领域老照片
    # （19 世纪原版人像，作者不详），否则整个项目的图全是风景、没有"人"。
    "liumingchuan": [
        # 引号里的 1/2 是同一场景的两次拍摄，这里取 1（详见 MAPPING 里的说明）
        find_src(LM_GJ, "宫保第”1"),
        find_src(LM_GJ, "肥西刘铭传故居"),
        os.path.join(OUT_ROOT, "_external", "liumingchuan_portrait.jpg"),
    ],
    "baogong": [
        # 连环画/皮影 + 包公祠实景照（CC BY-SA 3.0，见 assets/images/CREDITS.md）
        os.path.join(C, "BGGSImages", "巧断浮江尸.jpg"),
        os.path.join(C, "BGGSImages", "包公吃鱼.png"),
        os.path.join(OUT_ROOT, "_external", "baogong_temple.jpg"),
    ],
    "huobihua": [
        os.path.join(MAT, "文化馆项目资料整理", "火笔画", "火笔画申报书配套照片", f"{n:02d}.jpg")
        for n in (4, 6, 8)
    ],
    "wushantiezi": [
        os.path.join(M2, "吴山铁字", "吴山铁字照片 邓之元",
                     "邓华丽2020年于铁硏居拍摄，图为合肥第十四届国际文博会长丰县展区吴山铁字作品展.jpg"),
        os.path.join(M2, "吴山铁字", "吴山铁字照片 邓之元",
                     "邓华丽  2020年于吴山铁研居拍摄。图为铁硏居书法创作台，背景是吴山铁字工艺制作的《庆园春·雪》.jpg"),
        os.path.join(M2, "吴山铁字", "吴山铁字照片 邓之元",
                     "镇文广站工作人员2020年于铁硏居拍摄，图为省级非遗传承人邓之元为吴山小学的学生讲解吴山铁字的相关历史.jpg"),
    ],
}


def build_slides():
    """生成详情页主视图的轮播图（与详情页图不重复）"""
    print("\n[轮播图]")
    for slug, srcs in SLIDES.items():
        out_dir = os.path.join(OUT_ROOT, slug)
        # 先清掉旧的 slide*.jpg，避免源减少时残留多余图
        if os.path.isdir(out_dir):
            for f in os.listdir(out_dir):
                if f.startswith("slide") and f.lower().endswith((".jpg", ".png")):
                    os.remove(os.path.join(out_dir, f))
        for i, s in enumerate(srcs, 1):
            if not os.path.exists(s):
                print(f"  ✗ {slug} slide{i} 源缺失: {os.path.basename(s)}"); continue
            size, n = convert(s, os.path.join(out_dir, f"slide{i}.jpg"), DETAIL)
            print(f"  ✓ {slug}/slide{i}.jpg {size} {n//1024}KB  <- {os.path.basename(s)[:38]}")


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
        # 清掉多余的旧详情图：条目变少时（比如庐剧从 3 张减到 2 张）旧图会留在
        # 目录里，既占地方又容易让人以为还在用
        for f in os.listdir(out_dir) if os.path.isdir(out_dir) else []:
            stem, ext = os.path.splitext(f)
            if ext.lower() == ".jpg" and stem.isdigit() and int(stem) > len(spec["details"]):
                os.remove(os.path.join(out_dir, f))
                print(f"  - 清掉多余旧图 {f}")
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
    build_slides()
    print("\n== 缺失/待补 ==" if missing else "\n== 全部完成 ==")
    for m in missing:
        print("  ", m)


if __name__ == "__main__":
    main()
