import sys
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)
sys.path.insert(0, ".")
print("Importing...")
from src.ui.main_window import MainWindow
print("Creating...")
w = MainWindow()
print("OK")
w.close()
