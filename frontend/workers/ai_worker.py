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
    """
    segments = []
    cursor = 0.0
    total_s = duration_ms / 1000.0

    for sil in silence_list:
        s_start = sil["start"]
        s_end = sil["end"]

        if s_start > cursor + 0.05:
            segments.append({
                "start": int(cursor * 1000),
                "end":   int(s_start * 1000),
                "text":  "",
                "keep":  True,
            })

        segments.append({
            "start": int(s_start * 1000),
            "end":   int(s_end * 1000),
            "text":  "",
            "keep":  False,
        })
        cursor = s_end

    if cursor * 1000 < duration_ms - 100:
        segments.append({
            "start": int(cursor * 1000),
            "end":   duration_ms,
            "text":  "",
            "keep":  True,
        })

    return segments


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
            amplitudes.append(min(1.0, peak / 32768.0))
            if len(amplitudes) >= num_samples:
                break
        return amplitudes
    except Exception:
        return []


# ── 더미 폴백 (백엔드 의존성 없을 때) ──────────────────────────────────────

def _make_dummy_segments(duration_ms: int) -> list[dict]:
    dummy_texts = [
        "안녕하세요 오늘은 수학 문제를 풀어볼게요",
        "이 문제는 조금 까다롭지만 차근차근 보면",
        "먼저 조건을 정리해봅시다",
        "여기서 핵심은 이 부분이에요",
        "그러니까 이렇게 풀 수 있습니다",
        "다음 단계로 넘어가볼게요",
        "이 값을 대입하면",
        "최종 답은 이렇게 나옵니다",
        "이해가 되셨나요",
        "다음 문제도 같은 방식으로 접근하면 돼요",
    ]
    segments = []
    cursor = 0
    idx = 0
    while cursor < duration_ms - 3000:
        speech_len = random.randint(2000, 5000)
        end = min(cursor + speech_len, duration_ms)
        segments.append({"start": cursor, "end": end,
                          "text": dummy_texts[idx % len(dummy_texts)], "keep": True})
        cursor = end
        idx += 1
        if random.random() < 0.5:
            silence_len = random.randint(1000, 4000)
            silence_end = min(cursor + silence_len, duration_ms)
            segments.append({"start": cursor, "end": silence_end, "text": "", "keep": False})
            cursor = silence_end
        if cursor >= duration_ms:
            break
    return segments


def _make_dummy_amplitudes(segments: list[dict], duration_ms: int, num_samples: int = 2000) -> list[float]:
    amplitudes = [0.02] * num_samples
    for seg in segments:
        i_start = int(seg["start"] / duration_ms * num_samples)
        i_end = int(seg["end"] / duration_ms * num_samples)
        keep = seg.get("keep", True)
        for i in range(max(0, i_start), min(num_samples, i_end)):
            if keep:
                t = i / num_samples
                base = 0.45 + 0.35 * abs(math.sin(t * 120 + seg["start"] * 0.003))
                amplitudes[i] = max(0.1, min(1.0, base + random.uniform(-0.15, 0.15)))
            else:
                amplitudes[i] = random.uniform(0.0, 0.06)
    return amplitudes


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
                print("[DEBUG-C] _run_real 실행")
                self._run_real(duration_ms, BackendController)
            except ImportError as e:
                print(f"[DEBUG-C] _run_dummy 실행 (ImportError: {e})")
                self.status_changed.emit(f"⚠ 백엔드 모듈 없음 — 더미 모드로 실행 ({e})")
                self._run_dummy(duration_ms)

        except Exception as e:
            print(f"[DEBUG-D] exception: {e}")
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
            threshold = float(self._settings.get("silence_threshold", 0.3))
            result = bc.run_step1_extract_and_vad(
                self._video_path, temp_audio, temp_json,
                threshold=threshold,
            )
            if result is None:
                raise RuntimeError("VAD 분석 실패 — 오디오 추출을 확인해주세요")

            self.progress_updated.emit(80)
            self.status_changed.emit("파형 데이터 추출 중...")

            silence_list = result["silence_list"]
            print(f"[DEBUG-F] silence_list: {len(silence_list)}개, 첫항목: {silence_list[0] if silence_list else None}")
            segments = _convert_to_segments(silence_list, duration_ms)
            print(f"[DEBUG-F] segments: {len(segments)}개")
            amplitudes = _extract_amplitudes(temp_audio, duration_ms)

        self.progress_updated.emit(100)
        self.status_changed.emit("분석 완료")
        self.waveform_ready.emit(amplitudes, duration_ms)
        self.analysis_complete.emit(segments)

    # ── 더미 폴백 ─────────────────────────────────────────────────────────────

    def _run_dummy(self, duration_ms: int):
        self.status_changed.emit("무음 구간 감지 중... (VAD 시뮬레이션)")
        for p in range(10, 50, 5):
            self.progress_updated.emit(p)
            import time; time.sleep(0.15)

        self.status_changed.emit("구간 분석 중...")
        segments = _make_dummy_segments(duration_ms)
        for p in range(50, 85, 5):
            self.progress_updated.emit(p)
            import time; time.sleep(0.15)

        self.status_changed.emit("자막 생성 중... (STT 시뮬레이션)")
        for p in range(85, 101, 5):
            self.progress_updated.emit(p)
            import time; time.sleep(0.1)

        self.progress_updated.emit(100)
        self.status_changed.emit("분석 완료 (더미 모드)")
        amplitudes = _make_dummy_amplitudes(segments, duration_ms)
        self.waveform_ready.emit(amplitudes, duration_ms)
        self.analysis_complete.emit(segments)
