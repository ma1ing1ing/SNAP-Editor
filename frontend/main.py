import multiprocessing
import os
import sys


def _setup_ffmpeg_path():
    """
    번들 또는 개발 환경에서 FFmpeg 바이너리 경로를 PATH 앞에 추가.
    - 번들(frozen): sys._MEIPASS/bin/
    - 개발: 프로젝트 루트의 bin/ (없으면 시스템 ffmpeg 사용)
    """
    if getattr(sys, "frozen", False):
        bin_dir = os.path.join(sys._MEIPASS, "bin")
    else:
        # frontend/main.py → 프로젝트 루트
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bin_dir = os.path.join(project_root, "bin")

    if os.path.isdir(bin_dir):
        os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")


_setup_ffmpeg_path()

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication
from main_window import MainWindow


if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = QApplication(sys.argv)
    app.setStyle("macos")
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("white"))
    app.setPalette(palette)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
