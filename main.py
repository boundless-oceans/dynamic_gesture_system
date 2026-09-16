"""入口"""
import sys
from PySide6.QtWidgets import QApplication, QMessageBox
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

    # 权重不可用必须显式告警：否则程序照常启动，用一个随机初始化的模型
    # 输出看起来"挺像那么回事"的置信度，现场没人能发现是错的
    if win.recognizer.status != "ok":
        if win.recognizer.status == "missing":
            detail = "未找到模型权重文件：\n%s" % win.recognizer.status_detail
        else:
            detail = "模型权重加载失败：\n%s" % win.recognizer.status_detail
        QMessageBox.critical(
            win, "模型权重不可用",
            "%s\n\n手势识别已停用，界面可用鼠标操作。\n"
            "请将权重文件放入 weights/ 目录后重新启动。" % detail)

    sys.exit(app.exec())
