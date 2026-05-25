import time
import subprocess
import json
import math
import random
from PyQt6.QtCore import QThread, pyqtSignal


def _get_duration_ms(video_path: str) -> int:
    """ffprobe로 영상 길이(ms) 반환. 실패 시 300_000(5분) 기본값."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                video_path,
            ],
            capture_output=True, text=True, timeout=10,
        )
        data = json.loads(result.stdout)
        return int(float(data["format"]["duration"]) * 1000)
    except Exception:
        return 300_000


def _make_dummy_segments(duration_ms: int) -> list[dict]:
    """
    영상 길이 기반 더미 구간 생성.
    무음 구간(keep=False)과 발화 구간(keep=True)을 번갈아 배치.
    """
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
        # 발화 구간 2~5초
        speech_len = random.randint(2000, 5000)
        end = min(cursor + speech_len, duration_ms)
        segments.append({
            "start": cursor,
            "end": end,
            "text": dummy_texts[idx % len(dummy_texts)],
            "keep": True,
        })
        cursor = end
        idx += 1

        # 무음 구간 1~4초 (절반 확률로 삽입)
        if random.random() < 0.5:
            silence_len = random.randint(1000, 4000)
            silence_end = min(cursor + silence_len, duration_ms)
            segments.append({
                "start": cursor,
                "end": silence_end,
                "text": "",
                "keep": False,
            })
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


class AIWorker(QThread):

    progress_updated = pyqtSignal(int)
    status_changed = pyqtSignal(str)
    waveform_ready = pyqtSignal(list, int)   # (amplitudes, duration_ms)
    analysis_complete = pyqtSignal(list)
    error_occurred = pyqtSignal(str)

    def __init__(self, video_path: str, settings: dict):
        super().__init__()
        self._video_path = video_path
        self._settings = settings

    def run(self):
        try:
            # ── 1단계: 영상 길이 측정 ───────────────────────────────────────
            self.status_changed.emit("영상 정보 읽는 중...")
            self.progress_updated.emit(10)
            duration_ms = _get_duration_ms(self._video_path)
            time.sleep(0.4)

            # ── 2단계: VAD 시뮬레이션 ───────────────────────────────────────
            self.status_changed.emit("무음 구간 감지 중... (VAD)")
            for p in range(10, 50, 5):
                self.progress_updated.emit(p)
                time.sleep(0.15)

            # ── 3단계: 구간 생성 ────────────────────────────────────────────
            self.status_changed.emit("구간 분석 중...")
            segments = _make_dummy_segments(duration_ms)
            for p in range(50, 85, 5):
                self.progress_updated.emit(p)
                time.sleep(0.15)

            # ── 4단계: 자막 처리 시뮬레이션 ────────────────────────────────
            self.status_changed.emit("자막 생성 중... (STT)")
            for p in range(85, 101, 5):
                self.progress_updated.emit(p)
                time.sleep(0.1)

            # TODO: 백엔드 실제 연결 시 아래 주석 해제
            # import sys, os
            # sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../backend'))
            # from backend_controller import BackendController
            # bc = BackendController(
            #     progress_callback=lambda p: self.progress_updated.emit(p),
            #     log_callback=lambda m: self.status_changed.emit(m),
            # )
            # segments = bc.run_all(self._video_path, self._settings)

            self.progress_updated.emit(100)
            self.status_changed.emit("분석 완료")
            amplitudes = _make_dummy_amplitudes(segments, duration_ms)
            self.waveform_ready.emit(amplitudes, duration_ms)
            self.analysis_complete.emit(segments)

        except Exception as e:
            self.error_occurred.emit(str(e))
