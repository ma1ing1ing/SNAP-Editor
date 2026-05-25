import sys
import glob
from PyQt6 import uic
from PyQt6.QtWidgets import QApplication

app = QApplication(sys.argv)

OFFSET_X, OFFSET_Y = 40, 40
COL_WIDTH = 500

windows = []
for i, path in enumerate(sorted(glob.glob("frontend/*.ui"))):
    try:
        w = uic.loadUi(path)
        w.setWindowTitle(path)
        col = i % 3
        row = i // 3
        w.move(OFFSET_X + col * COL_WIDTH, OFFSET_Y + row * 360)
        w.show()
        w.raise_()
        windows.append(w)
        print(f"[OK] {path}")
    except Exception as e:
        print(f"[FAIL] {path}: {e}")

if not windows:
    print("표시할 .ui 파일이 없습니다.")
    sys.exit(0)

sys.exit(app.exec())
