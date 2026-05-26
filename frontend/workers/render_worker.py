import os
import sys
import re
import json
import tempfile
from typing import Optional
from PyQt6.QtCore import QThread, pyqtSignal


def _parse_srt(srt_path: str) -> list[dict]:
    """SRT 파일 파싱 → [{"start": ms, "end": ms, "text": str}]"""
    entries = []
    try:
        with open(srt_path, encoding="utf-8") as f:
            content = f.read()
        for block in re.split(r'\n\s*\n', content.strip()):
            lines = block.strip().splitlines()
            if len(lines) < 3:
                continue
            m = re.match(
                r'(\d{2}):(\d{2}):(\d{2}),(\d{3})\s-->\s(\d{2}):(\d{2}):(\d{2}),(\d{3})',
                lines[1]
            )
            if not m:
                continue
            h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
            start_ms = (h1 * 3600 + m1 * 60 + s1) * 1000 + ms1
            end_ms   = (h2 * 3600 + m2 * 60 + s2) * 1000 + ms2
            text = " ".join(lines[2:]).strip()
            entries.append({"start": start_ms, "end": end_ms, "text": text})
    except Exception:
        pass
    return entries


def _build_time_map(segments: list[dict]) -> list[tuple]:
    """
    편집 영상 시간 → 원본 시간 매핑 테이블.
    keep=True 구간만 편집 영상에 포함되므로, 각 구간의 편집 시간 범위를 계산.
    반환: [(edited_start_ms, edited_end_ms, original_start_ms), ...]
    """
    mapping = []
    edited_cursor = 0
    for seg in segments:
        if seg.get("keep", True):
            duration = seg["end"] - seg["start"]
            mapping.append((edited_cursor, edited_cursor + duration, seg["start"]))
            edited_cursor += duration
    return mapping


def _edited_to_original_ms(edited_ms: int, mapping: list[tuple]) -> int:
    """편집 영상의 특정 시간을 원본 영상 시간으로 변환."""
    for edited_start, edited_end, orig_start in mapping:
        if edited_start <= edited_ms <= edited_end:
            return orig_start + (edited_ms - edited_start)
    return -1


def _apply_cut_points(segments: list[dict], cut_points: list[dict]) -> list[dict]:
    """
    AI cut_points(불용어 구간)를 segments에 반영.
    cut_points의 start_seconds/end_seconds(초)를 ms로 변환해 겹치는 구간을 keep=False로 표시.
    """
    updated = [dict(seg) for seg in segments]
    for cp in cut_points:
        cp_start = int(cp.get("start_seconds", 0) * 1000)
        cp_end   = int(cp.get("end_seconds",   0) * 1000)
        for seg in updated:
            if seg["start"] < cp_end and seg["end"] > cp_start:
                seg["keep"]   = False
                seg["reason"] = "불용어"
    return updated


def _assign_text_to_segments(segments: list[dict], srt_entries: list[dict]) -> list[dict]:
    """
    SRT 항목(편집 영상 기준)을 원본 구간에 매핑하여 text 필드 업데이트.
    한 구간에 여러 SRT 항목이 걸리면 이어 붙임.
    """
    mapping = _build_time_map(segments)
    updated = [dict(seg) for seg in segments]

    # 기존 텍스트 초기화 (keep=True만)
    for seg in updated:
        if seg.get("keep", True):
            seg["text"] = ""

    for entry in srt_entries:
        orig_ms = _edited_to_original_ms(entry["start"], mapping)
        if orig_ms < 0:
            continue
        for seg in updated:
            if seg.get("keep", True) and seg["start"] <= orig_ms <= seg["end"]:
                seg["text"] = (seg["text"] + " " + entry["text"]).strip()
                break

    return updated


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

            from backend_controller import BackendController

            bc = BackendController(
                progress_callback=lambda p: self.progress_updated.emit(int(p * 0.5)),
                log_callback=lambda m: self.status_changed.emit(m),
            )

            data_dir     = os.path.normpath(os.path.join(os.path.dirname(__file__), "../../backend/Data"))
            edited_video = os.path.join(data_dir, "final_edited_video.mp4")
            subtitle_srt = os.path.join(data_dir, "subtitle.srt")
            final_result = self._output_path or os.path.join(data_dir, "final_with_subtitles.mp4")

            # 무음 구간(keep=False)만 추출 → 초 단위
            silence_list = [
                {"start": seg["start"] / 1000.0, "end": seg["end"] / 1000.0}
                for seg in self._segments
                if not seg.get("keep", True)
            ]

            # Step 3: 컷편집 렌더링 (silence JSON을 임시 파일로 전달)
            self.status_changed.emit("컷편집 렌더링 중...")
            self.progress_updated.emit(5)

            tmp_fd, tmp_json = tempfile.mkstemp(suffix=".json")
            try:
                with os.fdopen(tmp_fd, "w") as f:
                    json.dump(silence_list, f)
                result3 = bc.run_step3_render_video(self._video_path, tmp_json, edited_video)
            finally:
                os.unlink(tmp_json)

            if result3 is None:
                raise RuntimeError("컷편집 렌더링 실패")

            # Step 4: STT + 자막 생성
            self.status_changed.emit("자막 생성 중... (STT, 시간이 걸립니다)")
            self.progress_updated.emit(55)

            bc2 = BackendController(
                progress_callback=lambda p: self.progress_updated.emit(int(50 + p * 0.5)),
                log_callback=lambda m: self.status_changed.emit(m),
            )
            model_idx = int(self._settings.get("whisper_model", 2))
            whisper_model = self._MODELS[model_idx] if model_idx < len(self._MODELS) else "small"
            result4 = bc2.run_step4_stt_and_subtitle(edited_video, subtitle_srt, final_result,
                                                     whisper_model=whisper_model)
            if result4 is None:
                raise RuntimeError("STT 자막 생성 실패")

            # SRT 파싱 → 원본 구간에 텍스트 매핑
            srt_entries      = _parse_srt(subtitle_srt)
            updated_segments = _assign_text_to_segments(self._segments, srt_entries)

            # AI 불용어 cut_points → keep=False 반영
            cut_points = result4.get("cut_points", [])
            if cut_points:
                updated_segments = _apply_cut_points(updated_segments, cut_points)

            self.progress_updated.emit(100)
            self.status_changed.emit("렌더링 완료")
            self.render_complete.emit(final_result, updated_segments)

        except Exception as e:
            self.error_occurred.emit(str(e))
