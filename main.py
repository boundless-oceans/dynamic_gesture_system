"""入口"""
import sys

from src.logger import setup_logging

# ⚠ 必须排在其它 src.* 之前：config 等模块在**导入那一刻**就会打印
# （例如"[Config] 已应用本地调参…"），晚一步这些行就漏掉了。
# 打包成 --windowed 后控制台不存在，这些输出只有靠它才留得下来。
setup_logging()

from PySide6.QtWidgets import QApplication, QMessageBox
from src import paths
from src.ui.splash import create_splash

if __name__ == "__main__":
    app = QApplication(sys.argv)
    splash = create_splash()
    app.processEvents()

    # 数据目录写不进去的话，日志和「保存为默认」的现场调参都会**静默失效** ——
    # 而那种情况下日志本身也建不出来，所以弹窗是唯一的告知途径，不能只打一行日志
    problem = paths.check_writable()
    if problem:
        QMessageBox.warning(None, "数据目录不可写", problem)

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
