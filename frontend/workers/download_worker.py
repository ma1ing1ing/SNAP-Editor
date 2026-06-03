import os
import sys
from PyQt6.QtCore import QThread, pyqtSignal


class DownloadWorker(QThread):

    progress_updated  = pyqtSignal(int)
    status_changed    = pyqtSignal(str)
    download_complete = pyqtSignal(str)   # 다운로드된 로컬 파일 경로
    error_occurred    = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            backend_path = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "../../backend")
            )
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
