from PyQt6.QtCore import QThread, pyqtSignal


class AIWorker(QThread):

    progress_updated = pyqtSignal(int)       # 0~100
    status_changed = pyqtSignal(str)
    analysis_complete = pyqtSignal(list)     # list[dict] — 자막 세그먼트
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path: str, settings: dict):
        super().__init__()
        self._video_path = video_path
        self._settings = settings

    def run(self):
        try:
            self.status_changed.emit("AI 분석 중...")
            self.progress_updated.emit(0)

            # TODO: backend_controller 호출
            # from backend.backend_controller import run_pipeline
            # segments = run_pipeline(
            #     self._video_path,
            #     self._settings,
            #     on_progress=lambda p: self.progress_updated.emit(p),
            # )

            segments = []  # 백엔드 연결 전 빈 결과

            self.progress_updated.emit(100)
            self.status_changed.emit("분석 완료")
            self.analysis_complete.emit(segments)

        except Exception as e:
            self.error_occurred.emit(str(e))
