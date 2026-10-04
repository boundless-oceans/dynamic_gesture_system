"""3D 页的初始摆位（`pages/viewer.html` 里的 `initialPose`）

守的是**一个已经真出过的毛病**：古琴在 3D 页上是**从下往上仰望**的，而且几乎
总是"侧对着镜头 → 只剩一条边"。根因是原来的启发式只认一种扁法：

    if (maxDim / minDim > 5) { group.rotation.x -= 0.35; }   // 旧写法

相机与模型中心**等高**，所以"薄的是哪根轴"决定了你看到的是**面**还是**边**：
挂屏（薄轴 Z）面本来就朝着镜头，给点侧倾正好；而古琴是**平躺**的（薄轴 Y），
同一句话把它越推越歪，成了仰视。

这类坏法**不会报错、也不会让任何 Python 用例变红** —— 页面照常加载、日志照常打印，
只有现场盯着屏幕才看得出来。所以这里直接跑那段真 JS。

⚠ 本文件**不复制** JS 的规则到 Python 里。复制一份等于自证：JS 改坏了，
Python 那份还照着旧规则算，用例永远是绿的（这个项目在静态手势那边栽过一次）。
做法是把 `<script>` 抠出来交给 `node` 执行，问它要结果。

⚠ 没装 node 就整类跳过 —— 不应该为了这条守则给测试套件加一个硬依赖。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER = os.path.join(REPO, "pages", "viewer.html")
MODELS = os.path.join(REPO, "assets", "models")
NODE = shutil.which("node")

# 真实模型的包围盒尺寸（X, Y, Z），单位就是导出时的归一化单位。
# 数字来自 assets/models/<slug>.glb 里 POSITION accessor 的 min/max 之差；
# `test_尺寸表没写错` 会在模型在盘上时核对这份表有没有过期。
#
# ⚠ 走"极扁"那条分支的**有四个**，不止新加的这两个（当初也是只盯着新模型才会漏）：
#
#   guqin        (0.178, 0.073, 1.000)  薄轴 Y —— **平躺**，长边还正插向镜头
#   caihuitiejin (1.000, 0.997, 0.032)  薄轴 Z —— 站着，面朝镜头
#   huobihua     (0.414, 1.000, 0.033)  薄轴 Z —— 站着的画，面朝镜头
#   wushantiezi  (1.000, 0.422, 0.035)  薄轴 Z —— 站着的字，面朝镜头
#
# 后三个走的是"侧倾"分支，与改动前**逐字节一致**（`test_老模型的摆位一个都没变` 守着）。
SIZES = {
    "guqin":        (0.178, 0.073, 1.000),
    "caihuitiejin": (1.000, 0.997, 0.032),
    "huobihua":     (0.414, 1.000, 0.033),
    "wushantiezi":  (1.000, 0.422, 0.035),
    "hulu":         (0.384, 1.000, 0.384),
    "liumingchuan": (0.422, 1.000, 0.366),
    "baogong":      (0.815, 1.000, 0.315),
    "luju":         (0.385, 1.000, 0.357),
}

# 除古琴外**所有**模型：这次改动对它们必须是逐字不动的。
# 旧规则（`if 扁: rotation.x -= 0.35`）对它们算出来的就是正确答案，
# 所以这些模型新老结果必须完全相同 —— 这条是"别为了修古琴把别人碰坏"的守卫。
UNCHANGED_BY_FIX = ["caihuitiejin", "huobihua", "wushantiezi",
                    "hulu", "liumingchuan", "baogong", "luju"]

# 薄轴与视线方向的夹角下限：低于它就说明"基本是侧着看"。
#   古琴修复前 = 0.343（侧着，正是被报的那一条），修复后 = 0.964
EDGE_ON = 0.7


def _inline_script() -> str:
    """抠出 viewer.html 里内联的那段 JS，并去掉末尾的 `init();`

    去掉它是因为 `init()` 会去碰 DOM 和 WebGL —— 我们要的只是函数定义。
    """
    with open(VIEWER, encoding="utf-8") as f:
        html = f.read()
    blocks = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not blocks:
        raise AssertionError("viewer.html 里找不到内联 <script>")
    src = max(blocks, key=len)
    src, n = re.subn(r"^[ \t]*init\(\);[ \t]*$", "", src, flags=re.M)
    if not n:
        raise AssertionError("viewer.html 末尾没有 `init();` —— 抠出来的代码会真的去跑 WebGL")
    return src


def _run_initial_pose(sizes) -> list:
    """把尺寸交给**页面里那个真的 initialPose**，拿回它算出的摆位。

    THREE / window 只给最小桩：顶层只有 `new THREE.GLTFLoader()` 和
    `window.onresize = ...` 两句会碰到它们，其余都在函数体内。
    """
    harness = (
        "globalThis.THREE = { GLTFLoader: function () {} };\n"
        "globalThis.window = { innerWidth: 800, innerHeight: 600 };\n"
        + _inline_script()
        + "\nconst a = process.argv.slice(2).map(Number);\n"
        "const out = [];\n"
        "for (let i = 0; i + 2 < a.length; i += 3) { out.push(initialPose(a[i], a[i+1], a[i+2])); }\n"
        "console.log(JSON.stringify(out));\n"
    )
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "pose.js")
        with open(p, "w", encoding="utf-8") as f:
            f.write(harness)
        argv = [str(v) for t in sizes for v in t]
        r = subprocess.run([NODE, p] + argv, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise AssertionError("node 跑 viewer.html 的脚本失败：\n" + (r.stderr or "")[-800:])
    return json.loads((r.stdout or "").strip().splitlines()[-1])


def _apply(rot, v):
    """把 three.js 的欧拉角（XYZ 序 → R = Rx·Ry·Rz，这里 z 恒为 0）作用到向量上"""
    import math
    x, y, z = rot["x"], rot["y"], 0.0
    cx, sx = math.cos(x), math.sin(x)
    cy, sy = math.cos(y), math.sin(y)
    # 先 Ry 后 Rx
    vx, vy, vz = v[0] * cy + v[2] * sy, v[1], -v[0] * sy + v[2] * cy
    return vx, vy * cx - vz * sx, vy * sx + vz * cx


@unittest.skipUnless(NODE, "本机没有 node，跑不了页面里的 JS（这类守则跳过）")
class TestInitialPose(unittest.TestCase):

    def test_非扁模型不摆位(self):
        """hulu / baogong 这类正常立着的模型，一个字都不能动它"""
        got = _run_initial_pose([SIZES["hulu"], SIZES["baogong"]])
        for g, name in zip(got, ("hulu", "baogong")):
            with self.subTest(model=name):
                self.assertEqual(g["x"], 0)
                self.assertEqual(g["y"], 0)
                self.assertEqual(g["branch"], "-")

    def test_古琴是平躺的_要立起来而不是侧倾(self):
        """⚠ 这条就是当初那个 bug。

        旧写法对所有扁模型一律 `rotation.x -= 0.35`，古琴因此被推成**仰视 + 侧对镜头**。
        现在薄轴在 Y（平躺）走的是"立起来"，薄轴在 Z（面朝镜头）才走"侧倾"。
        """
        got = _run_initial_pose([SIZES["guqin"]])[0]
        self.assertIn("stand-up", got["branch"])
        self.assertGreater(got["x"], 0,
                           "平躺的模型要往**正**方向掀（负的就是从下往上仰望）")

    def test_挂屏仍然是侧倾(self):
        """彩绘贴金是薄在 Z 上的挂屏，面本来就朝镜头 —— 改成"立起来"会把它压扁"""
        got = _run_initial_pose([SIZES["caihuitiejin"]])[0]
        self.assertEqual(got["branch"], "lean")
        self.assertLess(got["x"], 0)

    def test_长边插向镜头的要先转开(self):
        """古琴的长边正好沿着 Z（冲着镜头），不先转开的话一上来只看得到端头"""
        got = _run_initial_pose([SIZES["guqin"]])[0]
        self.assertGreater(abs(got["y"]), 1.0, "初始转角太小，端头仍会正对镜头")

    def test_扁模型的薄轴最后要朝着镜头(self):
        """**这是判据本身**：扁模型必须让人看到"面"，不能是"一条边"。

        相机沿 −Z 看，所以薄轴与 Z 轴越平行，看到的面越正。
        拿修复前的古琴算一下只有 0.343（侧着）—— 低于下限，正是被报的那条。
        """
        flat = [n for n, s in SIZES.items() if max(s) / min(s) > 5]
        self.assertEqual(sorted(flat),
                         ["caihuitiejin", "guqin", "huobihua", "wushantiezi"],
                         "命中'极扁'分支的模型变了 —— 摆位规则要重新过一遍")
        for name in flat:
            with self.subTest(model=name):
                sx, sy, sz = SIZES[name]
                thin = min(range(3), key=lambda i: (sx, sy, sz)[i])
                axis = [0.0, 0.0, 0.0]
                axis[thin] = 1.0
                got = _run_initial_pose([SIZES[name]])[0]
                facing = abs(_apply(got, axis)[2])
                self.assertGreaterEqual(
                    facing, EDGE_ON,
                    "%s 的薄轴只有 %.3f 指着镜头 —— 基本是侧着看，只剩一条边" % (name, facing))

    def test_老模型的摆位一个都没变(self):
        """⚠ 修古琴不能顺手改到别人。

        旧规则是"凡是扁的就 `rotation.x -= 0.35`"。除古琴外所有模型在这条规则下
        本来就是对的（它们的面都朝着镜头），所以这次改动对它们必须**逐字不动**。
        哪天有人把分支写歪了，这条会立刻点名是哪个模型受了牵连。
        """
        for name in UNCHANGED_BY_FIX:
            with self.subTest(model=name):
                sx, sy, sz = SIZES[name]
                old_x = -0.35 if max(sx, sy, sz) / max(min(sx, sy, sz), 1e-6) > 5 else 0.0
                got = _run_initial_pose([SIZES[name]])[0]
                self.assertAlmostEqual(got["x"], old_x, places=9,
                                       msg="%s 的俯仰角变了 —— 那是旧规则下本来就对的值" % name)
                self.assertAlmostEqual(got["y"], 0.0, places=9,
                                       msg="%s 凭空多了个初始转角" % name)

    def test_尺寸表没写错(self):
        """拿真实 GLB 核对上面那张表。

        ⚠ 模型是 gitignore 的，所以"一个都没在盘上"才跳过；**只要盘上有就逐个核**，
        不能因为缺一个就把整条用例跳过 —— 那等于永远不检查。
        """
        if not os.path.isdir(MODELS) or not os.listdir(MODELS):
            self.skipTest("assets/models 未随版本库分发（.gitignore）")
        for name, expect in SIZES.items():
            p = os.path.join(MODELS, name + ".glb")
            if not os.path.exists(p):
                continue
            with self.subTest(model=name):
                got = _glb_size(p)
                for i, ax in enumerate("XYZ"):
                    self.assertAlmostEqual(
                        got[i], expect[i], delta=max(0.01, expect[i] * 0.05),
                        msg="%s 的 %s 轴与表里的 %s 对不上：模型是不是重新导出过？"
                            % (name, ax, expect[i]))


def _glb_size(path: str):
    """从 GLB 的 POSITION accessor 读包围盒尺寸（**glTF 坐标系**，不是 Blender 的）"""
    import json as _json
    import struct
    with open(path, "rb") as f:
        b = f.read()
    jlen = struct.unpack("<I", b[12:16])[0]
    j = _json.loads(b[20:20 + jlen].decode("utf-8"))
    mn, mx = [1e9] * 3, [-1e9] * 3
    for mesh in j["meshes"]:
        for pr in mesh["primitives"]:
            a = j["accessors"][pr["attributes"]["POSITION"]]
            for k in range(3):
                mn[k] = min(mn[k], a["min"][k])
                mx[k] = max(mx[k], a["max"][k])
    return [mx[k] - mn[k] for k in range(3)]


if __name__ == "__main__":
    unittest.main(verbosity=2)
