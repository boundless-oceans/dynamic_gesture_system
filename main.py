"""非遗动态手势展示系统 - 入口"""

import sys
from PySide6.QtWidgets import QApplication

from src.ui.main_window import MainWindow


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.start()
    win.show()
    sys.exit(app.exec())
