"""预览上的手势交互区

模型只处理画面中央一块（短边缩放 + 中心裁剪），四周根本看不到。预览上画的
那个框必须**精确等于模型能看到的范围**——画大了访客会把手伸到没用的地方，
画小了会把能用的区域圈掉。这个范围是从预处理参数算出来的，所以一旦预处理
改了、框却没跟着改，就会静默画偏。

因此这里不比对数字，而是拿**真实的预处理管线**去反证：
把框外的像素涂黑、框内涂白，喂进去；如果框是对的，模型看到的应当是一片纯白。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image

from src import config
from src.core.inference import GestureRecognizer, model_view_rect


def _real_transform():
    """拿到真实的预处理管线，但不构造模型（_build_transform 不依赖实例状态）"""
    return GestureRecognizer.__new__(GestureRecognizer)._build_transform()


def _crop_of_mask(frame_w, frame_h):
    """造一张"只有交互区内是白的"的图，返回模型看进去的张量"""
    img = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
    x, y, w, h = model_view_rect(frame_w, frame_h)
    img[int(round(y)):int(round(y + h)), int(round(x)):int(round(x + w))] = 255
    return _real_transform()([Image.fromarray(img)])


def _crop_with_marker(frame_w, frame_h, fx, fy, size=5):
    """在框内相对位置 (fx, fy) 放一个小白块，返回 (裁剪结果, 预期的裁剪内坐标)"""
    x, y, w, h = model_view_rect(frame_w, frame_h)
    px, py = x + fx * w, y + fy * h
    img = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
    x0, y0 = int(round(px - size / 2.0)), int(round(py - size / 2.0))
    img[y0:y0 + size, x0:x0 + size] = 255
    t = _real_transform()([Image.fromarray(img)])
    return t, (fx * config.INPUT_SIZE, fy * config.INPUT_SIZE)


class TestZoneMatchesPreprocessing(unittest.TestCase):
    """框必须精确等于模型能看到的范围

    直接断言"裁剪结果是一片纯白"是不行的：框的边界与裁剪边界重合，
    缩放的双线性插值必然blend出一条 1~2 像素的过渡带（实测白像素占 98.66%）。
    所以改成两条互补的判据——覆盖率卡"框不能画小"，标记点卡"坐标映射精确"。
    """

    def test_覆盖率_框没画小(self):
        for fw, fh in ((640, 480), (1280, 720), (320, 240)):
            with self.subTest(frame=(fw, fh)):
                a = _crop_of_mask(fw, fh)[0].numpy()
                white = float((a > a.max() * 0.98).mean())
                self.assertGreater(white, 0.95,
                                   f"{fw}x{fh} 框内白色只占 {white:.1%}，"
                                   "说明画出的交互区比模型实际看到的范围小")

    def test_标记点坐标映射精确(self):
        """框内 25% / 50% / 75% 处的标记，必须落在裁剪图的对应位置上"""
        for fw, fh in ((640, 480), (1280, 720)):
            for fx, fy in ((0.25, 0.25), (0.5, 0.5), (0.75, 0.75), (0.25, 0.75)):
                with self.subTest(frame=(fw, fh), at=(fx, fy)):
                    t, (ex, ey) = _crop_with_marker(fw, fh, fx, fy)
                    a = t[0].numpy()
                    gy, gx = np.unravel_index(int(np.argmax(a)), a.shape)
                    self.assertAlmostEqual(gx, ex, delta=3.0,
                                           msg=f"横向映射偏了：期望 {ex:.0f}，落在 {gx}")
                    self.assertAlmostEqual(gy, ey, delta=3.0,
                                           msg=f"纵向映射偏了：期望 {ey:.0f}，落在 {gy}")

    def test_框外的东西模型确实看不到(self):
        """框外放个高对比白块，模型输入应当与"全黑画面"逐像素一致（反证框没画大）

        注意不能拿"输入值接近 0"当判据：归一化后纯黑是 (0-mean)/std ≈ -2.12，
        本身就不是 0。要比的是"与全黑基线相同"。
        """
        for fw, fh in ((640, 480), (1280, 720)):
            with self.subTest(frame=(fw, fh)):
                tr = _real_transform()
                base = tr([Image.fromarray(np.zeros((fh, fw, 3), np.uint8))])[0].numpy()
                img = np.zeros((fh, fw, 3), dtype=np.uint8)
                img[5:45, 5:45] = 255                     # 左上角，落在框外
                a = tr([Image.fromarray(img)])[0].numpy()
                self.assertTrue(np.allclose(a, base, atol=1e-4),
                                "框外的高对比内容不该进入模型输入——说明框画大了")


class TestZoneGeometry(unittest.TestCase):

    def test_640x480下的具体范围(self):
        """把实测值钉住，便于对照"""
        x, y, w, h = model_view_rect(640, 480)
        self.assertEqual(round(w), 420)
        self.assertEqual(round(h), 420)
        self.assertEqual(round(x), 110)
        self.assertEqual(round(y), 30)

    def test_范围不超出画面(self):
        for fw, fh in ((640, 480), (320, 240), (1920, 1080), (480, 640)):
            with self.subTest(frame=(fw, fh)):
                x, y, w, h = model_view_rect(fw, fh)
                self.assertGreaterEqual(x, 0)
                self.assertGreaterEqual(y, 0)
                self.assertLessEqual(x + w, fw + 0.5)
                self.assertLessEqual(y + h, fh + 0.5)

    def test_范围居中(self):
        x, y, w, h = model_view_rect(640, 480)
        self.assertAlmostEqual(x, 640 - (x + w), delta=1.0)
        self.assertAlmostEqual(y, 480 - (y + h), delta=1.0)

    def test_退化输入不会崩(self):
        for fw, fh in ((0, 0), (-1, 100)):
            self.assertIsNotNone(model_view_rect(fw, fh))


class TestZoneOverlay(unittest.TestCase):
    """预览叠加层本身：不该崩，且开关能关掉"""

    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def test_绘制不崩且返回同尺寸画布(self):
        from PySide6.QtGui import QPixmap
        from src.ui.camera_widget import CameraWidget
        w = CameraWidget()
        pm = QPixmap(320, 240)
        pm.fill()
        out = w._draw_zone(pm, 640, 480)
        self.assertEqual((out.width(), out.height()), (320, 240))

    def test_关掉开关后画面不被改动(self):
        from PySide6.QtGui import QPixmap
        from src.ui.camera_widget import CameraWidget
        saved = config.CAMERA_SHOW_ZONE
        config.CAMERA_SHOW_ZONE = False
        try:
            w = CameraWidget()
            pm = QPixmap(320, 240)
            pm.fill()
            before = pm.toImage()
            out = w._draw_zone(pm, 640, 480)
            self.assertEqual(out.toImage(), before, "关掉开关后不该在画面上留任何痕迹")
        finally:
            config.CAMERA_SHOW_ZONE = saved

    def test_画了东西而不是原样返回(self):
        """反过来确认开关打开时确实画了内容（否则上面那条测试会假通过）"""
        from PySide6.QtGui import QPixmap
        from src.ui.camera_widget import CameraWidget
        saved = config.CAMERA_SHOW_ZONE
        config.CAMERA_SHOW_ZONE = True
        try:
            w = CameraWidget()
            pm = QPixmap(320, 240)
            pm.fill()
            before = pm.toImage()
            out = w._draw_zone(pm, 640, 480)
            self.assertNotEqual(out.toImage(), before, "开关打开时应当画出了交互区")
        finally:
            config.CAMERA_SHOW_ZONE = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
