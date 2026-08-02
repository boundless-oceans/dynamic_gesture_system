import sys; sys.path.insert(0,".")
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from src.ui.home_page import HomePage; print("1")
from src.ui.detail_page import DetailPage; print("2")
from src.ui.viewer_page import ViewerPage; print("3")
from src.ui.settings_page import SettingsPage; print("4")
from src.ui.camera_widget import CameraWidget; print("5")
from src.ui.main_window import MainWindow; print("6")

h = HomePage(); print("h ok")
d = DetailPage(); print("d ok")
v = ViewerPage(); print("v ok")
s = SettingsPage(); print("s ok")
