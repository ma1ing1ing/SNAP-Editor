import sys
from PyQt6.QtWidgets import QApplication, QMainWindow

app = QApplication(sys.argv)
window = QMainWindow()
window.show()
print("Test window shown")
sys.exit(app.exec())
