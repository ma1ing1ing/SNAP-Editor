import os
import sys
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal


class RenderWorker(QThread):

    progress_updated = pyqtSignal(int)
    status_changed   = pyqtSignal(str)
    render_complete  = pyqtSignal(str, list)   # (final_video_path, updated_segments)
    error_occurred   = pyqtSignal(str)

    _MODELS = ["tiny", "base", "small", "medium", "large"]

    def __init__(self, video_path: str, segments: list, settings: Optional[dict] = None, output_path: Optional[str] = None):
        super().__init__()
        self._video_path   = video_path
        self._segments     = segments
        self._settings     = settings or {}
        self._output_path  = output_path

    def run(self):
        try:
            backend_path = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "../../backend")
            )
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)

            from backend_controller import BackendController # type: ignore

            bc = BackendController(
                progress_callback=lambda p: self.progress_updated.emit(p),
                log_callback=lambda m: self.status_changed.emit(m),
            )

            data_dir     = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../backend/Data"))
            final_result = self._output_path or os.path.join(data_dir, "final_with_subtitles.mp4")

            self.status_changed.emit("최종 렌더링 및 자막 병합 중...")
            
            result = bc.run_final_render(
                input_video=self._video_path,
                segments=self._segments,
                output_video=final_result
            )

            if not result:
                raise RuntimeError("렌더링 실패")

            updated_segments = [dict(seg) for seg in self._segments]

            self.progress_updated.emit(100)
            self.status_changed.emit("렌더링 완료")
            self.render_complete.emit(final_result, updated_segments)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.error_occurred.emit(str(e))
