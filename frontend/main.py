import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.uic import loadUi

app = QApplication(sys.argv)

window = QMainWindow()
os.chdir(os.path.dirname(os.path.abspath(__file__)))
loadUi("main_window.ui", window)

window.show()
sys.exit(app.exec())
