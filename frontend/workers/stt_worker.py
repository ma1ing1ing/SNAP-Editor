import os
import sys
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


def _assign_stt_to_segments(segments: list[dict], stt_result: dict) -> list[dict]:
    """
    VAD keep=True 구간을 STT 문장 경계로 분리.
    keep=False(무음) 구간은 그대로 유지.
    """
    stt_segs = sorted(stt_result.get("segments", []), key=lambda s: s["start"])
    result = []

    for seg in segments:
        if not seg.get("keep", True):
            result.append(dict(seg))
            continue

        # 이 VAD 구간과 겹치는 STT 문장 추출
        matching = [
            s for s in stt_segs
            if int(s["end"] * 1000) > seg["start"] and int(s["start"] * 1000) < seg["end"]
        ]

        if not matching:
            result.append(dict(seg))
            continue

        cursor = seg["start"]
        for stt in matching:
            stt_start = max(int(stt["start"] * 1000), seg["start"])
            stt_end   = min(int(stt["end"]   * 1000), seg["end"])

            if stt_start - cursor > 100:
                result.append({**seg, "start": cursor, "end": stt_start, "text": ""})

            result.append({**seg, "start": stt_start, "end": stt_end, "text": stt.get("text", "").strip()})
            cursor = stt_end

        if seg["end"] - cursor > 100:
            result.append({**seg, "start": cursor, "end": seg["end"], "text": ""})

    return result


class STTWorker(QThread):

    progress_updated = pyqtSignal(int)
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

            from backend_controller import BackendController

            model_idx     = int(self._settings.get("whisper_model", 2))
            whisper_model = self._MODELS[model_idx] if model_idx < len(self._MODELS) else "small"

            bc = BackendController(
                progress_callback=lambda p: self.progress_updated.emit(p),
                log_callback=lambda m: self.status_changed.emit(m),
            )

            with tempfile.TemporaryDirectory() as tmp:
                srt_path = os.path.join(tmp, "subtitle.srt")
                stt_result, _ = bc.run_step2_stt(
                    self._video_path, srt_path, whisper_model
                )

            updated = _assign_stt_to_segments(self._segments, stt_result)
            self.status_changed.emit("자막 생성 완료")
            self.stt_complete.emit(updated)

        except Exception as e:
            self.error_occurred.emit(str(e))
