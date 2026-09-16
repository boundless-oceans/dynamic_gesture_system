"""FBX → GLB 批量转换（供 viewer.html 用 three.js 加载）

用法（普通 Python 运行即可，会自动调用 Blender 无头模式）：
    python tools/fbx_to_glb.py                # 转换全部 6 个项目
    python tools/fbx_to_glb.py hulu luju      # 只转指定项目

源素材在 F 盘资料里（本机路径，见 JOBS），产物写到 assets/models/<slug>.glb。
本文件同时充当 Blender 侧的 worker：被 Blender 调用时（--background --python 本文件 -- 源 目标）
只做单个文件的导入/导出。
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "assets", "models")

BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"

# 源 FBX（本机 F 盘资料）
_U = r"F:\非遗资料\_extracted\yuanma\LuZhouFeiYi_2019.4.30\Assets\Model"
_W = r"F:\非遗资料\文化馆二期\lzfy-models\models"
JOBS = {
    "hulu":          os.path.join(_U, "hulu", "hulu.fbx"),
    "liumingchuan":  os.path.join(_U, "liumingchuan", "刘铭传.fbx"),
    "baogong":       os.path.join(_U, "baogong", "包公2.fbx"),
    "luju":          os.path.join(_U, "luju", "庐剧94.fbx"),
    "huobihua":      os.path.join(_U, "huobihua", "火笔画94.fbx"),
    "wushantiezi":   os.path.join(_W, "wushantiezi", "wushantiezi.FBX"),
}


def _convert_one(src: str, dst: str):
    """在 Blender 里执行（blender --background --python 本文件 -- src dst）"""
    import bpy  # noqa: 仅在 Blender 内可用

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB", export_apply=True)
    print("OK ->", dst)


def main():
    argv = sys.argv
    if "bpy" in sys.modules or "--" in argv:  # Blender worker 模式
        try:
            args = argv[argv.index("--") + 1:]
        except ValueError:
            args = []
        if len(args) >= 2:
            _convert_one(args[0], args[1])
            return

    # 驱动模式
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or list(JOBS)
    if not os.path.exists(BLENDER):
        print("未找到 Blender:", BLENDER)
        return
    os.makedirs(OUT_DIR, exist_ok=True)
    for name in names:
        src = JOBS.get(name)
        if not src:
            print(f"[{name}] 未知项目，跳过"); continue
        if not os.path.exists(src):
            print(f"[{name}] ✗ 源缺失: {src}"); continue
        dst = os.path.join(OUT_DIR, f"{name}.glb")
        print(f"[{name}] 转换中... {os.path.getsize(src)/1024/1024:.1f}MB")
        r = subprocess.run([BLENDER, "--background", "--python", os.path.abspath(__file__),
                            "--", src, dst], capture_output=True, text=True)
        ok = os.path.exists(dst)
        print(f"[{name}] {'✓' if ok else '✗'} {dst if ok else r.stdout[-500:]}")


if __name__ == "__main__":
    main()
