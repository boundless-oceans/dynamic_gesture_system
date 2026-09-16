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


TARGET_SIZE = 1.0   # 归一化后每个模型的最大边长


def _convert_one(src: str, dst: str):
    """在 Blender 里执行（blender --background --python 本文件 -- src dst）

    步骤：导入 FBX → 烘焙骨骼姿态为静态网格 → 删除骨架/空物体 →
          居中到原点 → 统一缩放到最大边长 TARGET_SIZE → 导出 GLB。
    这样导出的模型尺寸/位置一致，three.js 里量包围盒不会出偏差。
    """
    import bpy  # noqa: 仅在 Blender 内可用
    from mathutils import Vector, Matrix

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src)

    # 1) 网格对象：convert 会应用修改器（含 Armature），把姿态烘焙成静态网格
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    if meshes:
        bpy.context.view_layer.objects.active = meshes[0]
        bpy.ops.object.convert(target="MESH")

    # 2) 删除非网格对象（骨架、空物体、灯光、相机）
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o, do_unlink=True)

    # 3) 世界坐标包围盒 → 中心与最大边长
    mn = Vector((1e18,) * 3)
    mx = Vector((-1e18,) * 3)
    for o in bpy.context.scene.objects:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            w = o.matrix_world @ Vector(c)
            mn = Vector((min(mn[i], w[i]) for i in range(3)))
            mx = Vector((max(mx[i], w[i]) for i in range(3)))
    if not bpy.context.scene.objects:
        print("WARN: 未导入到任何网格", src)
    center = (mn + mx) / 2
    size = mx - mn
    s = TARGET_SIZE / max(size) if max(size) > 0 else 1.0

    # 4) 先平移使中心归零，再整体缩放（绕原点），最后把变换烘进网格数据
    M = Matrix.Scale(s, 4) @ Matrix.Translation(-center)
    for o in bpy.context.scene.objects:
        o.matrix_world = M @ o.matrix_world
    bpy.ops.object.select_all(action="SELECT")
    if bpy.context.scene.objects:
        bpy.context.view_layer.objects.active = bpy.context.scene.objects[0]
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    os.makedirs(os.path.dirname(dst), exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=dst, export_format="GLB")
    print("OK -> %s | 原尺寸=%s 缩放=%.4f" % (dst, tuple(round(v, 2) for v in size), s))


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
