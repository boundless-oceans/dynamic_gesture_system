"""静态手势模型（HaGRID 34 类 ResNet18）：类别表、预处理、绑定策略

这里测的都是**坏了不会报错**的东西：

  * **类别顺序** —— 索引与权重强绑定，改错一位之后模型照常输出、"看着挺像"，
    只是所有结果都错位了。所以把 34 项整个钉死
  * **预处理几何** —— 缩放/补边的位置算错，模型仍然会给一个"看起来很正常"的概率
    （而且是错的）。拿合成图把像素位置钉住
  * **绑定策略** —— 架构 A 的全部安全感在于"判成没绑定的类就弃权"。
    一旦有人顺手多绑几个，静态与动态的手型冲突就会真的发生
  * **权重缺失时的行为** —— 必须是"静默不启用"，不能崩、也不能拿随机权重硬跑

不需要摄像头；只有最后一类用例需要权重文件（没有就跳过）。
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import config
from src.core.gesture_mapper import CONTROL_GESTURES, STATIC_TO_CONTROL
from src.core.static_gesture import (
    IMG_SIZE, LABELS, MEAN, NO_GESTURE, NUM_CLASSES, PAD_VALUE, STD,
    StaticGestureRecognizer, action_for, preprocess,
)

WEIGHTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "weights", "hagrid_resnet18.pth")

# ⚠ 这几个**写死，不引用模块常量**。
#   引用的话就成了自证：把模块里的常量改错，用例的期望值跟着一起错，永远是绿的。
#   （变异验证实际抓到过 —— 把 mean 换成 ImageNet 那组，用例照样全过。）
#   值来自素材项目 configs/ResNet18.yaml 的 dataset.img_mean / img_std。
MEAN_LITERAL = np.array([0.54, 0.499, 0.474], dtype=np.float32)
STD_LITERAL = np.array([0.234, 0.235, 0.231], dtype=np.float32)


def _norm(v: int) -> np.ndarray:
    """某个 0~255 的灰度值经过 Normalize 之后，三个通道各自的值"""
    return (v / 255.0 - MEAN_LITERAL) / STD_LITERAL


class TestLabelTable(unittest.TestCase):
    """34 类的顺序 **与权重文件强绑定** —— 错一位，所有输出整体错位"""

    def test_类别表就是配置里那一份(self):
        self.assertEqual(LABELS, [
            "grabbing", "grip", "holy", "point", "call", "three3", "timeout", "xsign",
            "hand_heart", "hand_heart2", "little_finger", "middle_finger", "take_picture",
            "dislike", "fist", "four", "like", "mute", "ok", "one", "palm", "peace",
            "peace_inverted", "rock", "stop", "stop_inverted", "three", "three2", "two_up",
            "two_up_inverted", "three_gun", "thumb_index", "thumb_index2", "no_gesture",
        ])
        self.assertEqual(NUM_CLASSES, 34)

    def test_三个关键下标(self):
        """权重是 34 类（fc.weight 形状 [34, 512]），这三个下标都已核对过。"""
        self.assertEqual(LABELS.index("like"), 16)
        self.assertEqual(LABELS.index("ok"), 18)
        self.assertEqual(NO_GESTURE, 33)
        self.assertEqual(LABELS[NO_GESTURE], "no_gesture")

    def test_类别名不重复(self):
        self.assertEqual(len(set(LABELS)), NUM_CLASSES, "类别名有重复，映射会串")


class TestPreprocess(unittest.TestCase):
    """几何必须与配置里的 test_transforms 一致：
    LongestMaxSize(224) → PadIfNeeded(224, 灰 144) → Normalize

    算错位置的话模型**照样输出一个看着很正常的概率**，只是它是错的 ——
    所以拿合成图把像素位置钉住。
    """

    def test_输出形状(self):
        out = preprocess(np.zeros((480, 640, 3), dtype=np.uint8))
        self.assertEqual(tuple(out.shape), (1, 3, IMG_SIZE, IMG_SIZE))

    def test_横图上下补灰边(self):
        """448×224（长边 448）→ 缩到 224×112 → 上下各补 56 行"""
        img = np.full((224, 448, 3), 100, dtype=np.uint8)
        out = preprocess(img)[0].numpy()
        pad = _norm(PAD_VALUE)
        content = _norm(100)
        for c in range(3):
            self.assertAlmostEqual(out[c, 0, 0], pad[c], places=4, msg="第 0 行该是灰边")
            self.assertAlmostEqual(out[c, 55, 0], pad[c], places=4, msg="第 55 行该是灰边")
            self.assertAlmostEqual(out[c, 56, 0], content[c], places=4, msg="第 56 行该是图")
            self.assertAlmostEqual(out[c, 167, 0], content[c], places=4, msg="第 167 行该是图")
            self.assertAlmostEqual(out[c, 168, 0], pad[c], places=4, msg="第 168 行该是灰边")
            self.assertAlmostEqual(out[c, 223, 0], pad[c], places=4, msg="最后一行该是灰边")

    def test_竖图左右补灰边(self):
        """224×448（长边 448）→ 缩到 112×224 → 左右各补 56 列"""
        img = np.full((448, 224, 3), 100, dtype=np.uint8)
        out = preprocess(img)[0].numpy()
        pad, content = _norm(PAD_VALUE), _norm(100)
        for c in range(3):
            self.assertAlmostEqual(out[c, 0, 0], pad[c], places=4)
            self.assertAlmostEqual(out[c, 0, 167], content[c], places=4, msg="中间该是图")
            self.assertAlmostEqual(out[c, 0, 223], pad[c], places=4)

    def test_方图不补边(self):
        img = np.full((224, 224, 3), 100, dtype=np.uint8)
        out = preprocess(img)[0].numpy()
        content = _norm(100)
        for c in range(3):
            self.assertAlmostEqual(out[c, 0, 0], content[c], places=4,
                                   msg="方图不该有任何灰边")

    def test_大图缩到224而不是裁(self):
        """长边超过 224 时是**整体缩下去**，不是裁中间一块"""
        img = np.full((448, 448, 3), 100, dtype=np.uint8)
        out = preprocess(img)[0].numpy()
        content = _norm(100)
        for c in range(3):
            self.assertAlmostEqual(out[c, 0, 0], content[c], places=4)
            self.assertAlmostEqual(out[c, 223, 223], content[c], places=4)

    def test_均值方差常量本身没被改错(self):
        """⚠ 必须断言**字面值**：这些常量是照着素材项目那份 yaml 抄的，
        改动它们不会报任何错，只会让识别率悄悄变差。"""
        np.testing.assert_allclose(MEAN, [0.54, 0.499, 0.474], atol=1e-6)
        np.testing.assert_allclose(STD, [0.234, 0.235, 0.231], atol=1e-6)

    def test_归一化用的是静态模型那一组均值方差(self):
        """⚠ 与动态模型那组（ImageNet）**不同**，混用不会报错、只会悄悄变差。

        拿一幅纯白图验：三个通道归一化之后的值应当各不相同
        （因为 mean/std 三个通道不同），且等于 (1 - mean) / std。
        """
        out = preprocess(np.full((224, 224, 3), 255, dtype=np.uint8))[0].numpy()
        expect = (1.0 - MEAN_LITERAL) / STD_LITERAL
        self.assertGreater(abs(expect[0] - expect[2]), 0.1,
                           "前提：这三组 mean/std 确实互不相同")
        for c in range(3):
            self.assertAlmostEqual(out[c, 0, 0], expect[c], places=4)
        # 顺带确认**没有**误用 ImageNet 那组
        self.assertNotAlmostEqual(out[0, 0, 0], (1.0 - 0.485) / 0.229, places=2)

    def test_灰边值来自配置(self):
        self.assertEqual(PAD_VALUE, 144, "PadIfNeeded 的填充值是 144（中灰）")


class TestBindingPolicy(unittest.TestCase):
    """架构 A：静态模型**只做加法** —— 只认 ok / 点赞，其余一律弃权

    ⚠ 为什么只绑这两个：两个模型吃的是**同一块画面**，同一个手型会同时喂进两边。
    所以只要静态类的手型撞上在用的动态手势，两边的判断就会被同一只手同时点燃、
    产生两个互相矛盾的意图。ok / like 恰好是唯一不冲突的两个。
    """

    def test_只绑了两个(self):
        self.assertEqual(set(STATIC_TO_CONTROL), {"ok", "like"})

    def test_职责划分(self):
        self.assertEqual(STATIC_TO_CONTROL["ok"], "home")     # OK → 返回首页
        self.assertEqual(STATIC_TO_CONTROL["like"], "guide")  # 点赞 → 手势说明页

    def test_绑定的都是合法控制手势(self):
        for label, ctrl in STATIC_TO_CONTROL.items():
            with self.subTest(label=label):
                self.assertIn(ctrl, CONTROL_GESTURES)

    def test_绑定的键都是真实类别(self):
        for label in STATIC_TO_CONTROL:
            self.assertIn(label, LABELS, f"{label} 不在 34 类表里")

    def test_手型冲突的那几类必须弃权(self):
        """⚠ 这几类**必须**保持不绑 —— 它们的手型与在用的动态手势撞车：

            palm/stop/five 五指张开 ⚔ G07 张开两次（→ 放大）
            fist           握拳     ⚔ G11 缩小
            point/one      伸食指   ⚔ B0A 单指指向、G01 单击
            peace/two_up   两指     ⚔ B0B 双指指向、G09 双指双击（→ 旋转模型）

        访客做动态手势时，静态模型看到的就是这些手型 —— 一旦绑上，
        "张开两次放大"就会同时触发一个静态动作。
        """
        for label in ("palm", "stop", "fist", "point", "one",
                      "peace", "peace_inverted", "two_up", "two_up_inverted"):
            with self.subTest(静态类=label):
                self.assertIsNone(action_for(label, 0.99),
                                  f"{label} 与在用的动态手势手型冲突，不能绑")

    def test_绝不能绑的那几类(self):
        """展台上误触发会很难看，而且对访客毫无操作意义。

        它们**在模型里是存在的** —— 写这条用例是为了让后来的人知道
        "是有意排除的"，而不是漏了。
        """
        for label in ("middle_finger", "dislike", "three_gun"):
            with self.subTest(静态类=label):
                self.assertIsNone(action_for(label, 0.99))

    def test_比心不可行因为要两只手(self):
        """HaGRID 的 hand_heart / hand_heart2 是**双手**比心，
        展台上访客很少双手一起比，绑了也没人能用。"""
        for label in ("hand_heart", "hand_heart2"):
            self.assertIsNone(action_for(label, 0.99))

    def test_变体类不碰(self):
        """同类手势被拆成好几个近似类，模型自己也分不清"""
        for label in ("three", "three2", "three3", "thumb_index", "thumb_index2"):
            self.assertIsNone(action_for(label, 0.99))

    def test_no_gesture不触发(self):
        self.assertIsNone(action_for("no_gesture", 0.99))


class TestActionFor(unittest.TestCase):
    """门槛判定（纯函数）"""

    def setUp(self):
        self._saved = config.STATIC_CONFIDENCE_THRESHOLD
        config.STATIC_CONFIDENCE_THRESHOLD = 0.75

    def tearDown(self):
        config.STATIC_CONFIDENCE_THRESHOLD = self._saved

    def test_未达门槛返回None(self):
        self.assertIsNone(action_for("ok", 0.74))

    def test_恰好等于门槛算成立(self):
        """与动态那边一致：正好等于门槛算"成立"（`>=`）"""
        self.assertEqual(action_for("ok", 0.75), "home")

    def test_超过门槛返回动作(self):
        self.assertEqual(action_for("ok", 0.99), "home")
        self.assertEqual(action_for("like", 0.80), "guide")

    def test_None也能处理(self):
        self.assertIsNone(action_for(None, 0.99))
        self.assertIsNone(action_for("ok", None))

    def test_门槛比动态那边严(self):
        """⚠ 这不是笔误：静态姿势被**持续观测**（推理每 0.6 秒一次），
        错过一帧的成本是零；而动态手势一次只有一发。"""
        self.assertGreater(config.STATIC_CONFIDENCE_THRESHOLD,
                           config.CONFIDENCE_THRESHOLD)


class TestRecognizerWithoutWeights(unittest.TestCase):
    """权重缺失时必须**静默不启用** —— 不能崩，也不能拿随机权重硬跑

    （随机初始化的 resnet18 照样输出"看着挺像"的概率，是最难排查的一种坏法。）
    """

    def setUp(self):
        self._saved = config.STATIC_WEIGHTS_PATH
        config.STATIC_WEIGHTS_PATH = os.path.join(
            os.path.dirname(WEIGHTS), "___不存在的权重___.pth")

    def tearDown(self):
        config.STATIC_WEIGHTS_PATH = self._saved

    def test_状态是missing(self):
        r = StaticGestureRecognizer()
        self.assertEqual(r.status, "missing")
        self.assertFalse(r.model, "权重不在，不该建出模型")

    def test_predict返回None而不是抛异常(self):
        r = StaticGestureRecognizer()
        self.assertIsNone(r.predict(np.zeros((480, 640, 3), dtype=np.uint8)))

    def test_空帧也不炸(self):
        r = StaticGestureRecognizer()
        self.assertIsNone(r.predict(np.zeros((0, 0, 3), dtype=np.uint8)))
        self.assertIsNone(r.predict(None))


@unittest.skipUnless(os.path.exists(WEIGHTS),
                     "静态手势权重未随版本库分发（.gitignore），跳过")
class TestRecognizerWithWeights(unittest.TestCase):
    """权重在的时候：能载入、能出结果、结果结构对得上

    ⚠ 这里**不断言识别准不准** —— 准不准要靠真人对着摄像头测
    （tests/manual/measure_static_gesture.py），拿合成图断言"这是 ok"
    是自欺欺人。只碰"结构坏了会静默出错"的地方。
    """

    @classmethod
    def setUpClass(cls):
        cls.r = StaticGestureRecognizer()

    def test_权重载入成功(self):
        self.assertEqual(self.r.status, "ok",
                         f"权重状态异常: {self.r.status_detail}")

    def test_输出结构与类别一致(self):
        out = self.r.predict(np.full((480, 640, 3), 128, dtype=np.uint8))
        self.assertIsNotNone(out)
        self.assertIn(out["label"], LABELS)
        self.assertEqual(out["index"], LABELS.index(out["label"]))
        self.assertGreaterEqual(out["confidence"], 0.0)
        self.assertLessEqual(out["confidence"], 1.0)
        self.assertEqual(len(out["top3"]), 3)
        # top3 的概率必须是降序的（取错方向的话 top1 其实是 top3）
        probs = [c for _, c in out["top3"]]
        self.assertEqual(probs, sorted(probs, reverse=True))
        self.assertEqual(out["top3"][0][0], out["label"])

    def test_两张不同的图给出不同的结果(self):
        """⚠ 这条是为了挡住"其实没跑模型、返回了个常量"这类坏法。

        拿两幅差别极大的合成图（纯黑 vs 棋盘），top1 或置信度必须不一样。
        """
        a = self.r.predict(np.zeros((480, 640, 3), dtype=np.uint8))
        checker = np.indices((480, 640)).sum(0) % 2
        b = self.r.predict(np.repeat((checker * 255).astype(np.uint8)[:, :, None], 3, axis=2))
        self.assertTrue(a["label"] != b["label"] or a["confidence"] != b["confidence"],
                        "两幅完全不同的图给出了完全相同的结果 —— 模型没真的在跑")


if __name__ == "__main__":
    unittest.main(verbosity=2)
