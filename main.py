"""入口"""
import sys
from PySide6.QtWidgets import QApplication
from src.ui.splash import create_splash

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = create_splash()
    app.processEvents()

    from src.ui.main_window import MainWindow
    win = MainWindow()

    splash.finish(win)
    win.start()
    win.show()
    sys.exit(app.exec())
