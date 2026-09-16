"""手工冒烟：完整应用（等同 python main.py，但不动入口文件）

直接 `python tests/manual/smoke_app.py` 运行。用来人工过一遍
六个页面的实际观感、手势路由和摄像头悬浮窗位置。

自动化测试里不跑这个：它会开真窗口、启动摄像头和推理，且需要人来判断画面。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.start()
    win.show()
    print("[冒烟] 主窗口已启动")
    print("  - 权重状态:", win.recognizer.status)
    print("  - 6 个页面：传承人 / 首页 / 详情 / 3D / 设置 / 地图")
    print("  - 用鼠标点按钮，或直接做手势；右上角是摄像头悬浮窗")
    sys.exit(app.exec())
