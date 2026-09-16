"""数据与素材的一致性

最容易踩的一类坑：加了一个非遗项目却忘了加 slug，或者改了项目顺序却没同步素材目录——
这类错误不会报错，只会让某张图/某个模型悄悄消失。

注意：weights/、assets/models/、assets/videos/ 都在 .gitignore 里，
干净克隆里本就为空，所以这几项用 skipUnless 跳过，而不是判失败。
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core import project_assets as PA
from src.core.project_data import PROJECTS


def _json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
INHERITORS = _json(os.path.join(ASSETS, "inheritors.json"))["items"]


def _dir_has(d, suffix):
    return os.path.isdir(d) and any(fn.lower().endswith(suffix) for fn in os.listdir(d))


class TestProjectsAndSlugs(unittest.TestCase):

    def test_项目数与slug数一致(self):
        """数量不一致会让最后几个项目的素材全部错位"""
        self.assertEqual(len(PROJECTS), len(PA.SLUGS),
                         f"projects.json 有 {len(PROJECTS)} 项，SLUGS 有 {len(PA.SLUGS)} 个")

    def test_每个项目必填字段齐全(self):
        for i, p in enumerate(PROJECTS):
            for field in ("name", "category", "inheritor", "summary", "intro", "sections"):
                self.assertIn(field, p, f"第 {i} 项 {p.get('name')} 缺字段 {field}")
                self.assertTrue(p[field], f"第 {i} 项 {field} 为空")

    def test_越界索引返回空串不抛异常(self):
        n = len(PROJECTS)
        self.assertEqual(PA.slug_of(n), "")
        self.assertEqual(PA.thumb_path(n), "")
        self.assertEqual(PA.model_path(-1), "")
        self.assertEqual(PA.slide_paths(n), [])


class TestImageAssets(unittest.TestCase):
    """图片是随版本库分发的，所以这里断言必须存在"""

    def test_卡片图与详情图齐全(self):
        for i, p in enumerate(PROJECTS):
            with self.subTest(project=p["name"]):
                self.assertTrue(os.path.exists(PA.thumb_path(i)), f"{p['name']} 缺 thumb.jpg")
                for k in (1, 2, 3):
                    self.assertTrue(os.path.exists(PA.detail_path(i, k)),
                                    f"{p['name']} 缺 {k}.jpg")

    def test_轮播图非空且照片排在渲染图前(self):
        for i, p in enumerate(PROJECTS):
            with self.subTest(project=p["name"]):
                slides = PA.slide_paths(i)
                self.assertTrue(slides, f"{p['name']} 没有轮播图")
                for s in slides:
                    self.assertTrue(os.path.exists(s), f"轮播图缺失: {s}")
                names = [os.path.basename(s) for s in slides]
                renders = [n for n in names if n.startswith("render")]
                if renders:
                    first_render = names.index(renders[0])
                    photos = [n for n in names if n.startswith("slide")]
                    self.assertEqual(names[:first_render], photos, "照片应排在 3D 渲染图之前")

    def test_传承人配图缺失时回退到卡片图(self):
        for i in range(len(PROJECTS)):
            p = PA.portrait_path(i)
            self.assertTrue(os.path.exists(p), f"portrait_path({i}) 指向不存在的文件: {p}")

    def test_二维码只在有素材的项目上返回(self):
        for i, p in enumerate(PROJECTS):
            qr = PA.qr_path(i)
            if qr:
                self.assertTrue(os.path.exists(qr), f"{p['name']} 二维码路径不存在")
                self.assertTrue(qr.endswith("qr.png"))

    def test_不存在的名字返回空串(self):
        self.assertEqual(PA.inheritor_photo("不存在的人.jpg"), "")
        self.assertEqual(PA.inheritor_video("不存在的人.mp4"), "")


class TestInheritors(unittest.TestCase):

    def test_条目字段齐全(self):
        self.assertTrue(INHERITORS, "inheritors.json 为空")
        for i, it in enumerate(INHERITORS):
            for field in ("name", "project", "bio"):
                self.assertIn(field, it, f"第 {i} 条缺字段 {field}")
                self.assertTrue(it[field], f"第 {i} 条的 {field} 为空")

    def test_可以没有视频但要有名字(self):
        for it in INHERITORS:
            v = PA.inheritor_video(it.get("video", ""))
            if v:
                self.assertTrue(os.path.exists(v))

    @unittest.skipUnless(_dir_has(os.path.join(ASSETS, "videos", "inheritors"), ".mp4"),
                         "assets/videos 未随版本库分发（.gitignore），跳过")
    def test_声明的视频文件都存在(self):
        for it in INHERITORS:
            if it.get("video"):
                self.assertTrue(
                    os.path.exists(os.path.join(ASSETS, "videos", "inheritors", it["video"])),
                    f"{it['name']} 声明的视频 {it['video']} 不存在")


class TestModelAssets(unittest.TestCase):

    @unittest.skipUnless(_dir_has(os.path.join(ASSETS, "models"), ".glb"),
                         "assets/models 未随版本库分发（.gitignore），跳过")
    def test_每个项目的3D模型都在(self):
        for i, p in enumerate(PROJECTS):
            path = PA.model_path(i)
            self.assertTrue(os.path.exists(path), f"{p['name']} 缺 {os.path.basename(path)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
