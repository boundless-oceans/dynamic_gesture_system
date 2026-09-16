"""页面不可见时不应在后台解码视频

背景：DetailPage / InheritorPage 在应用启动时就会被构造出来（此时并不可见）。
如果构造函数里直接 play()，就会在后台解码一整段几分钟的视频（还带音轨），
白白占 CPU —— 展台上这些算力本该留给推理。

QMediaPlayer 是 Qt 层对象，不像网页里的 requestAnimationFrame 那样会被
按可见性自动停掉，所以必须由我们自己控制。
"""
import os
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import QApplication

_app = None

IDLE = (QMediaPlayer.StoppedState, QMediaPlayer.PausedState)


def setUpModule():
    global _app
    _app = QApplication.instance() or QApplication(sys.argv)


def _pump(seconds=0.5):
    """播放状态是异步变化的，得给事件循环一点时间"""
    end = time.time() + seconds
    while time.time() < end:
        _app.processEvents()
        time.sleep(0.01)


def _state(player):
    return None if player is None else player.playbackState()


class TestDetailPageIdle(unittest.TestCase):

    def test_构造时不播放(self):
        from src.ui.detail_page import DetailPage
        d = DetailPage()          # 默认项目 baogong，有视频
        _pump()
        self.assertIsNotNone(d._player, "该断言前提是默认项目确实有视频")
        self.assertIn(_state(d._player), IDLE,
                      "页面不可见时不应在后台播放视频")

    def test_切到视频子页才播放(self):
        from src.ui.detail_page import DetailPage
        d = DetailPage()
        d.show(); _pump()
        self.assertIn(_state(d._player), IDLE, "主视图上不该播视频")

        d.stack.setCurrentIndex(1)          # 切到"非遗详情"子页
        _pump()
        self.assertEqual(_state(d._player), QMediaPlayer.PlayingState,
                         "进入视频子页后应开始播放")

    def test_离开页面会暂停(self):
        from src.ui.detail_page import DetailPage
        d = DetailPage()
        d.show(); _pump()
        d.stack.setCurrentIndex(1); _pump()
        self.assertEqual(_state(d._player), QMediaPlayer.PlayingState)

        d.hide(); _pump()
        self.assertIn(_state(d._player), IDLE, "离开页面应暂停，否则又会后台解码")

    def test_无视频的项目不建播放器(self):
        from src.ui.detail_page import DetailPage
        from src.core import project_assets as PA
        d = DetailPage()
        no_video = [i for i in range(6) if not PA.video_path(i)]
        self.assertTrue(no_video, "该断言前提是确实有项目缺视频")
        d.set_project(no_video[0]); _pump()
        self.assertIsNone(d._player)


class TestInheritorPageIdle(unittest.TestCase):

    def test_构造时不播放(self):
        from src.ui.inheritor_page import InheritorPage
        p = InheritorPage()
        _pump()
        self.assertIsNotNone(p._player, "该断言前提是首位传承人确实有视频")
        self.assertIn(_state(p._player), IDLE,
                      "页面不可见时不应在后台播放视频")

    def test_可见时播放_隐藏时暂停(self):
        from src.ui.inheritor_page import InheritorPage
        p = InheritorPage()
        p.show(); _pump()
        self.assertEqual(_state(p._player), QMediaPlayer.PlayingState,
                         "页面可见时应播放")

        p.hide(); _pump()
        self.assertIn(_state(p._player), IDLE, "页面隐藏后应暂停")

    def test_页面可见时切换传承人仍继续播放(self):
        """切换传承人会重建播放器——重建后必须自己恢复播放，
        否则会出现"翻到下一人视频就不动了"。"""
        from src.ui.inheritor_page import InheritorPage
        p = InheritorPage()
        p.show(); _pump()
        p.next_person(); _pump()
        self.assertEqual(_state(p._player), QMediaPlayer.PlayingState,
                         "可见状态下切换传承人后应继续播放")


if __name__ == "__main__":
    unittest.main(verbosity=2)
