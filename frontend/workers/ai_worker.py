import os
import sys
import struct
import subprocess
import json
import math
import random
import tempfile
from PyQt6.QtCore import QThread, pyqtSignal


def _get_duration_ms(video_path: str) -> int:
    """ffprobe로 영상 길이(ms) 반환. 실패 시 300_000(5분) 기본값."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", video_path],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        return int(float(data["format"]["duration"]) * 1000)
    except Exception:
        return 300_000


def _convert_to_segments(silence_list: list[dict], duration_ms: int) -> list[dict]:
    """
    백엔드 반환값(무음 구간, 초 단위) → 프론트 형식(전체 구간, ms 단위).
    발화 구간(keep=True)과 무음 구간(keep=False)을 교차 배치.
    전체 타임라인(0 ~ duration_ms)을 빈틈 없이 커버하도록 보장.
    """
    # 1. 정렬 + 겹침 병합
    silences = sorted(silence_list, key=lambda s: s["start"])
    merged = []
    for sil in silences:
        if merged and sil["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], sil["end"])
        else:
            merged.append({"start": sil["start"], "end": sil["end"]})

    # 2. 무음/발화 구간 생성
    segments = []
    cursor = 0.0
    for sil in merged:
        s_start = sil["start"]
        s_end   = sil["end"]
        if s_start > cursor + 0.05:
            segments.append({"start": int(cursor * 1000), "end": int(s_start * 1000), "text": "", "keep": True})
        segments.append({"start": int(s_start * 1000), "end": int(s_end * 1000), "text": "", "keep": False})
        cursor = s_end

    if cursor * 1000 < duration_ms - 100:
        segments.append({"start": int(cursor * 1000), "end": duration_ms, "text": "", "keep": True})

    # 3. 후처리: 정렬 후 남은 gap을 keep=True로 채움 (VAD 누락 구간 보완)
    segments.sort(key=lambda s: s["start"])
    filled = []
    prev_end = 0
    for seg in segments:
        if seg["start"] > prev_end + 100:   # 100ms 이상 gap → 발화로 채움
            filled.append({"start": prev_end, "end": seg["start"], "text": "", "keep": True})
        filled.append(seg)
        prev_end = max(prev_end, seg["end"])

    if prev_end < duration_ms - 100:
        filled.append({"start": prev_end, "end": duration_ms, "text": "", "keep": True})

    return filled


def _extract_amplitudes(audio_path: str, duration_ms: int, num_samples: int = 2000) -> list[float]:
    """ffmpeg로 오디오 raw PCM 추출 → 진폭 envelope 반환 (0.0~1.0)."""
    try:
        cmd = [
            "ffmpeg", "-i", audio_path,
            "-f", "s16le", "-ac", "1", "-ar", "8000",
            "pipe:1", "-loglevel", "quiet",
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=60)
        raw = result.stdout
        if not raw:
            return []

        n = len(raw) // 2
        samples = struct.unpack(f"{n}h", raw[: n * 2])
        chunk = max(1, len(samples) // num_samples)
        amplitudes = []
        for i in range(0, len(samples) - chunk + 1, chunk):
            peak = max(abs(s) for s in samples[i : i + chunk])
            amplitudes.append(peak)
            
        if amplitudes:
            # 전체 구간 중 가장 큰 소리(max_amp)를 찾아서 그 기준으로 비율을 맞춤 (정규화)
            max_amp = max(amplitudes)
            # 녹음 소리가 아예 없는 경우(1000 이하) 무한정 커지는 것을 방지
            scale = 32768.0 if max_amp < 1000 else max_amp
            amplitudes = [min(1.0, a / scale) for a in amplitudes]
            
        return amplitudes
    except Exception:
        return []


# ── Worker ──────────────────────────────────────────────────────────────────

class AIWorker(QThread):

    progress_updated = pyqtSignal(int)
    status_changed   = pyqtSignal(str)
    waveform_ready   = pyqtSignal(list, int)   # (amplitudes, duration_ms)
    analysis_complete = pyqtSignal(list)
    error_occurred   = pyqtSignal(str)

    def __init__(self, video_path: str, settings: dict):
        super().__init__()
        self._video_path = video_path
        self._settings = settings

    def run(self):
        try:
            self.status_changed.emit("영상 정보 읽는 중...")
            self.progress_updated.emit(5)
            duration_ms = _get_duration_ms(self._video_path)

            # 백엔드 경로 등록
            backend_path = os.path.normpath(
                os.path.join(os.path.dirname(__file__), "../../backend")
            )
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)

            try:
                from backend_controller import BackendController
                self._run_real(duration_ms, BackendController)
            except ImportError as e:
                self.status_changed.emit(f"⚠ 백엔드 모듈 없음 — 더미 모드로 실행 ({e})")
                self._run_dummy(duration_ms)

        except Exception as e:
            self.error_occurred.emit(str(e))

    # ── 백엔드 연동 ──────────────────────────────────────────────────────

    def _run_real(self, duration_ms: int, BackendController):
        bc = BackendController(
            progress_callback=lambda p: self.progress_updated.emit(int(10 + p * 0.7)),
            log_callback=lambda m: self.status_changed.emit(m),
        )

        with tempfile.TemporaryDirectory() as tmp:
            temp_audio = os.path.join(tmp, "audio.wav")
            temp_json  = os.path.join(tmp, "silence.json")

            # Step 1: 오디오 추출 + VAD
            threshold = float(self._settings.get("silence_threshold", 0.5))
            min_silence_ms = int(self._settings.get("min_silence_ms", 500))
            result = bc.run_step1_extract_and_vad(
                self._video_path, temp_audio, temp_json,
                threshold=threshold,
                min_silence_ms=min_silence_ms,
            )
            if result is None:
                raise RuntimeError("VAD 분석 실패 — 오디오 추출을 확인해주세요")

            self.progress_updated.emit(80)
            self.status_changed.emit("파형 데이터 추출 중...")

            silence_list = result["silence_list"]
            print(f"\n[DEBUG] silence_list ({len(silence_list)}개):")
            for s in silence_list:
                print(f"  silence {s['start']:.2f}s ~ {s['end']:.2f}s ({s['end']-s['start']:.2f}s)")
            segments = _convert_to_segments(silence_list, duration_ms)
            print(f"\n[DEBUG] segments ({len(segments)}개):")
            for s in segments:
                tag = "KEEP" if s["keep"] else "REMOVE"
                print(f"  {tag} {s['start']}ms ~ {s['end']}ms")
            amplitudes = _extract_amplitudes(temp_audio, duration_ms)

        self.progress_updated.emit(100)
        self.status_changed.emit("분석 완료")
        self.waveform_ready.emit(amplitudes, duration_ms)
        self.analysis_complete.emit(segments)

    # ── 더미 모드 (백엔드 없을 때) ──────────────────────────────────────
    def _run_dummy(self, duration_ms: int):
        self.status_changed.emit("더미 모드: 가상 구간 생성 중...")
        self.progress_updated.emit(30)

        # 10초 간격으로 발화/무음 구간을 교차 생성
        chunk = 10_000
        segments = []
        t = 0
        while t < duration_ms:
            end = min(t + chunk, duration_ms)
            is_keep = (t // chunk) % 2 == 0
            segments.append({"start": t, "end": end, "text": "", "keep": is_keep})
            t = end

        # 평탄한 더미 파형
        amplitudes = [0.3 + 0.1 * math.sin(i * 0.1) for i in range(2000)]

        self.progress_updated.emit(100)
        self.status_changed.emit("⚠ 더미 모드 완료 — 실제 분석이 아닙니다")
        self.waveform_ready.emit(amplitudes, duration_ms)
        self.analysis_complete.emit(segments)
