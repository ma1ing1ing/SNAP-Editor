import os
import sys
from PyQt6.QtCore import QThread, pyqtSignal


def _get_backend_path() -> str:
    """개발 환경과 PyInstaller 번들 환경 모두에서 backend 경로를 반환."""
    if getattr(sys, "frozen", False):
        # PyInstaller 번들: _MEIPASS 기준
        return os.path.join(sys._MEIPASS, "backend")
    # 개발 환경: 파일 위치 기준 상대 경로
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "../../backend"))


class DownloadWorker(QThread):

    progress_updated  = pyqtSignal(int)
    status_changed    = pyqtSignal(str)
    download_complete = pyqtSignal(str)
    error_occurred    = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            backend_path = _get_backend_path()
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)

            from download_video import download_video

            output_dir = os.path.join(backend_path, "Data")

            self.status_changed.emit("영상 정보 확인 중...")
            self.progress_updated.emit(0)

            def on_progress(pct: int):
                self.progress_updated.emit(pct)
                self.status_changed.emit(f"다운로드 중... {pct}%")

            path = download_video(self._url, output_dir, progress_callback=on_progress)

            self.status_changed.emit("다운로드 완료")
            self.download_complete.emit(path)

        except Exception as e:
            self.error_occurred.emit(str(e))
