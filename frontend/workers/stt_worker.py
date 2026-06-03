import os
import sys
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


def _assign_stt_to_segments(segments: list[dict], stt_result: dict) -> list[dict]:
    """
    STT 문장을 기준 단위로 구간 재구성. (Timeline Sweep 방식)
    - 1순위: STT 문장 (전체 삽입, 내부에 겹친 무음은 무시)
    - 2순위: VAD 무음 (STT가 없는 곳에 위치한 무음)
    - 3순위: 둘 다 없는 갭 (keep=True인 빈 텍스트 구간)
    """
    # 1. 원본 segments에서 총 길이 계산
    max_end = max((s.get("end", 0) for s in segments), default=0)
    
    # 2. VAD 무음 추출 및 정렬
    silences = sorted(
        [seg for seg in segments if not seg.get("keep", True)],
        key=lambda s: s["start"]
    )
    
    # 3. STT 결과 ms 변환 및 정렬
    stt_segs = sorted(stt_result.get("segments", []), key=lambda s: s["start"])
    processed_stts = []
    for s in stt_segs:
        start_ms = int(s["start"] * 1000)
        end_ms = int(s["end"] * 1000)
        if start_ms < end_ms:
            processed_stts.append({
                "start": start_ms,
                "end": end_ms,
                "text": s.get("text", "").strip(),
                "keep": True
            })

    if not processed_stts and not silences:
        # 둘 다 없으면 기본 구간 그대로 반환
        return segments

    result = []
    cursor = 0
    stt_idx = 0
    sil_idx = 0

    while cursor < max_end:
        # 현재 커서 이후의 유효한 stt/silence 찾기
        while stt_idx < len(processed_stts) and processed_stts[stt_idx]["end"] <= cursor:
            stt_idx += 1
        while sil_idx < len(silences) and silences[sil_idx]["end"] <= cursor:
            sil_idx += 1

        next_stt = processed_stts[stt_idx] if stt_idx < len(processed_stts) else None
        next_sil = silences[sil_idx] if sil_idx < len(silences) else None

        # 1순위: 커서가 STT 구간 내에 있음
        if next_stt and next_stt["start"] <= cursor < next_stt["end"]:
            # STT 구간 전체를 삽입 (커서가 중간이더라도 남은 구간 전부 삽입)
            # 단, max_end를 넘어가지 않게 방어
            segment_end = min(next_stt["end"], max_end)
            result.append({
                "start": cursor,
                "end": segment_end,
                "text": next_stt["text"],
                "keep": True
            })
            cursor = segment_end
            stt_idx += 1
            continue

        # 2순위: 커서가 무음 구간 내에 있음
        if next_sil and next_sil["start"] <= cursor < next_sil["end"]:
            # 무음을 삽입하되, 무음 도중 STT가 시작되면 거기까지만 자름
            segment_end = min(next_sil["end"], max_end)
            if next_stt and next_stt["start"] < segment_end:
                segment_end = next_stt["start"]
            
            result.append({
                "start": cursor,
                "end": segment_end,
                "keep": False
            })
            cursor = segment_end
            continue

        # 3순위: 커서가 STT도 무음도 아닌 Gap에 있음
        # 다음 STT 시작과 다음 무음 시작 중 더 가까운 곳까지 갭으로 채움
        next_events = []
        if next_stt: next_events.append(next_stt["start"])
        if next_sil: next_events.append(next_sil["start"])
        
        if next_events:
            segment_end = min(min(next_events), max_end)
        else:
            segment_end = max_end
            
        result.append({
            "start": cursor,
            "end": segment_end,
            "text": "",
            "keep": True
        })
        cursor = segment_end

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

            model_idx     = int(self._settings.get("whisper_model", 3))
            whisper_model = self._MODELS[model_idx] if model_idx < len(self._MODELS) else "medium"

            bc = BackendController(
                progress_callback=lambda p: self.progress_updated.emit(p),
                log_callback=lambda m: self.status_changed.emit(m),
            )

            with tempfile.TemporaryDirectory() as tmp:
                srt_path = os.path.join(tmp, "subtitle.srt")
                stt_result = bc.run_step2_stt(
                    self._video_path, srt_path, whisper_model
                )

            updated = _assign_stt_to_segments(self._segments, stt_result)
            self.status_changed.emit("자막 생성 완료")
            self.stt_complete.emit(updated)

        except Exception as e:
            self.error_occurred.emit(str(e))
            