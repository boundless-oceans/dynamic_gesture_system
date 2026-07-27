"""测试 F4: 主窗口（4页框架 + 摄像头悬浮窗 + 手势路由）"""

import sys
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.start()
    win.show()
    print("[F4 Test] 主窗口已启动")
    print("  - 4 页切换可用鼠标点击按钮")
    print("  - 摄像头悬浮右上角")
    print("  - 推理线程运行中")
    sys.exit(app.exec())
