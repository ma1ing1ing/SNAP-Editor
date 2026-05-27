import os
import sys
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


def _assign_stt_to_segments(segments: list[dict], stt_result: dict) -> list[dict]:
    """STT 결과(초 단위)를 segments(ms 단위)의 text 필드에 매핑."""
    updated = [dict(seg) for seg in segments]
    for stt_seg in stt_result.get("segments", []):
        start_ms = int(stt_seg["start"] * 1000)
        text = stt_seg.get("text", "").strip()
        if not text:
            continue
        for seg in updated:
            if seg.get("keep", True) and seg["start"] <= start_ms <= seg["end"]:
                seg["text"] = (seg["text"] + " " + text).strip()
                break
    return updated


class STTWorker(QThread):

    status_changed  = pyqtSignal(str)
    stt_complete    = pyqtSignal(list)   # updated segments
    error_occurred  = pyqtSignal(str)

    _MODELS = ["tiny", "base", "small", "medium", "large"]

    def __init__(self, video_path: str, segments: list, settings: dict):
        super().__init__()
        self._video_path = video_path
        self._segments   = segments
        self._settings   = settings

    def run(self):
        try:
            backend_path = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "../../backend")
            )
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)

            from transcriber import transcribe_video_to_srt

            model_idx     = int(self._settings.get("whisper_model", 2))
            whisper_model = self._MODELS[model_idx] if model_idx < len(self._MODELS) else "small"

            self.status_changed.emit(f"자막 생성 중... (Whisper {whisper_model})")

            with tempfile.TemporaryDirectory() as tmp:
                srt_path = os.path.join(tmp, "subtitle.srt")
                _, _, stt_result, _ = transcribe_video_to_srt(
                    self._video_path, srt_path, model_size=whisper_model
                )

            updated = _assign_stt_to_segments(self._segments, stt_result)
            self.status_changed.emit("자막 생성 완료")
            self.stt_complete.emit(updated)

        except Exception as e:
            self.error_occurred.emit(str(e))
            