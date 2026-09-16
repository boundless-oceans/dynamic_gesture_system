"""用 Blender 把 3D 模型渲染成详情页轮播图（用于缺少高清照片的项目）。

用法：
    python tools/render_slides.py                # 渲染 NEED 里列出的项目
    python tools/render_slides.py liumingchuan   # 只渲染指定项目

产物：assets/images/<slug>/render1.jpg、render2.jpg（与照片轮播共存，与详情页图不重复）
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(REPO, "assets", "models")
OUT = os.path.join(REPO, "assets", "images")
BLENDER = r"C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"

# 需要渲染轮播图的项目（原照片分辨率不足）
NEED = ["hulu"]
W, H = 1200, 800

_WORKER = r'''
import bpy, sys, math, mathutils, os
argv = sys.argv[sys.argv.index("--")+1:]
src, out, ang = argv[0], argv[1], float(argv[2])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=src)
objs=[o for o in bpy.context.scene.objects if o.type=="MESH"]
mn=mathutils.Vector((1e18,)*3); mx=mathutils.Vector((-1e18,)*3)
for o in objs:
    for c in o.bound_box:
        w=o.matrix_world @ mathutils.Vector(c)
        mn=mathutils.Vector((min(mn[i],w[i]) for i in range(3)))
        mx=mathutils.Vector((max(mx[i],w[i]) for i in range(3)))
center=(mn+mx)/2; size=mx-mn; maxd=max(size) or 1
cam_d=bpy.data.cameras.new("c"); cam=bpy.data.objects.new("c",cam_d)
bpy.context.scene.collection.objects.link(cam)
dist=maxd*2.0
a=math.radians(ang)
cam.location=center+mathutils.Vector((math.sin(a)*dist, -math.cos(a)*dist, dist*0.28))
cam.rotation_mode="QUATERNION"
cam.rotation_quaternion=(center-cam.location).to_track_quat("-Z","Y")
bpy.context.scene.camera=cam
for pos,en in (((2,-2,3),5.0),((-2,2,2),2.5)):
    ld=bpy.data.lights.new("s","SUN"); ld.energy=en
    lo=bpy.data.objects.new("s",ld); bpy.context.scene.collection.objects.link(lo)
    lo.rotation_euler=(math.radians(55), 0, math.radians(pos[0]*20))
sc=bpy.context.scene
sc.render.engine="CYCLES"; sc.cycles.samples=48; sc.cycles.device="CPU"
sc.render.resolution_x, sc.render.resolution_y = %d, %d
sc.render.film_transparent=False
sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes=True
sc.world.node_tree.nodes["Background"].inputs[0].default_value=(0.93,0.94,0.96,1)
sc.render.filepath=out
bpy.ops.render.render(write_still=True)
print("RENDER ok:", out)
''' % (W, H)


def render_one(slug, ang, out_png):
    src = os.path.join(MODELS, f"{slug}.glb")
    if not os.path.exists(src):
        print("  源缺失:", src); return False
    tmp = os.path.join(os.environ.get("TEMP", "."), "_render_worker.py")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(_WORKER)
    r = subprocess.run([BLENDER, "--background", "--python", tmp, "--", src, out_png, str(ang)],
                       capture_output=True, text=True)
    ok = os.path.exists(out_png)
    if not ok:
        print("  渲染失败:", r.stdout[-300:])
    return ok


def main():
    names = [a for a in sys.argv[1:] if not a.startswith("-")] or NEED
    from PIL import Image
    for slug in names:
        print(f"[{slug}]")
        for i, ang in enumerate((18, 55), 1):
            out_png = os.path.join(os.environ.get("TEMP", "."), f"_slide_{slug}_{i}.png")
            if not render_one(slug, ang, out_png):
                continue
            dst = os.path.join(OUT, slug, f"render{i}.jpg")
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            with Image.open(out_png) as im:
                im.convert("RGB").save(dst, "JPEG", quality=90, optimize=True)
            print(f"  ✓ {slug}/render{i}.jpg  <- 3D 渲染 (角度 {ang}°)")


if __name__ == "__main__":
    main()
