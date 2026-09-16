"""项目素材路径管理（图片 / 3D 模型）

slug 顺序与 assets/projects.json 的项目顺序一一对应，
素材由 tools/prepare_assets.py 生成、模型由 tools/fbx_to_glb.py 生成。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
IMAGES_DIR = os.path.join(ROOT, "assets", "images")
MODELS_DIR = os.path.join(ROOT, "assets", "models")

SLUGS = ["hulu", "liumingchuan", "baogong", "luju", "huobihua", "wushantiezi"]


def slug_of(index: int) -> str:
    """项目序号 → slug（越界返回空串）"""
    return SLUGS[index] if 0 <= index < len(SLUGS) else ""


def thumb_path(index: int) -> str:
    """卡片图路径"""
    s = slug_of(index)
    return os.path.join(IMAGES_DIR, s, "thumb.jpg") if s else ""


def detail_path(index: int, i: int) -> str:
    """详情图路径（i 从 1 开始）"""
    s = slug_of(index)
    return os.path.join(IMAGES_DIR, s, f"{i}.jpg") if s else ""


def model_path(index: int) -> str:
    """3D 模型（.glb）路径"""
    s = slug_of(index)
    return os.path.join(MODELS_DIR, f"{s}.glb") if s else ""
