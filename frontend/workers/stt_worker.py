import os
import sys
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


def _assign_stt_to_segments(segments: list[dict], stt_result: dict) -> list[dict]:
    """
    STT 문장을 기준 단위로 구간 재구성.
    - keep=True 행: STT 문장 1개 = 테이블 행 1개
    - keep=False 행: 문장 사이 VAD 무음 구간
    - 문장 내부의 VAD 무음(짧은 일시정지)은 문장과 함께 처리
    """
    stt_segs = sorted(stt_result.get("segments", []), key=lambda s: s["start"])
    silences = sorted(
        [seg for seg in segments if not seg.get("keep", True)],
        key=lambda s: s["start"]
    )

    if not stt_segs:
        return segments

    result = []
    si = 0  # silence pointer

    for stt in stt_segs:
        stt_start_ms = int(stt["start"] * 1000)
        stt_end_ms   = int(stt["end"]   * 1000)
        text = stt.get("text", "").strip()

        if stt_start_ms >= stt_end_ms:
            continue

        # 이 STT 문장 시작 전에 끝나는 무음 구간 삽입
        while si < len(silences) and silences[si]["end"] <= stt_start_ms:
            result.append(dict(silences[si]))
            si += 1

        # STT 문장 전체를 하나의 행으로 추가
        result.append({"start": stt_start_ms, "end": stt_end_ms, "text": text, "keep": True})

        # 문장 범위 내 무음은 내부 일시정지로 간주하고 건너뜀
        while si < len(silences) and silences[si]["start"] < stt_end_ms:
            si += 1

    # 마지막 STT 이후 남은 무음 추가
    while si < len(silences):
        result.append(dict(silences[si]))
        si += 1

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
            stopword_mode = self._settings.get("stopword_mode", "default")

            bc = BackendController(
                progress_callback=lambda p: self.progress_updated.emit(p),
                log_callback=lambda m: self.status_changed.emit(m),
            )

            with tempfile.TemporaryDirectory() as tmp:
                srt_path = os.path.join(tmp, "subtitle.srt")
                stt_result, _ = bc.run_step2_stt(
                    self._video_path, srt_path, whisper_model, stopword_mode
                )

            updated = _assign_stt_to_segments(self._segments, stt_result)
            self.status_changed.emit("자막 생성 완료")
            self.stt_complete.emit(updated)

        except Exception as e:
            self.error_occurred.emit(str(e))
