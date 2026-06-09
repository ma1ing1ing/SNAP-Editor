# SNAP-Editor 코드 분석 문서

> 최종 업데이트: 2026-06-09  
> 분석 범위: frontend/, backend/ 전체

---

## 1. 전체 아키텍처

### 파이프라인 흐름

```
[사용자] → 파일 열기 / URL 입력
              ↓
        [MainWindow] (PyQt6 GUI)
              ↓
        [AIWorker] QThread
              ↓
    [BackendController]
       ├── extract_audio.py   → WAV 추출 (FFmpeg, aresample=async=1)
       ├── export_json.py     → Silero VAD → silence_list
       └── (결과 반환)
              ↓
        [WaveformWidget] 파형 + 구간 표시
              ↓
        [STTWorker] QThread
              ↓
    [BackendController.run_step2_stt]
       └── transcriber.py     → stable-whisper → SRT
              ↓
    [_assign_stt_to_segments]  → STT 기반 구간 재조립
              ↓
        [사용자 구간 편집] (O/X, 자막 수정, 구간 추가/병합)
              ↓
        [RenderWorker] QThread
              ↓
    [BackendController.run_final_render]
       ├── editor.py          → FFmpeg 컷편집 (CRF 18, medium preset)
       ├── SRT 생성 (stretch_ratio 보정)
       └── editor.py          → 자막 병합 (c:v copy)
```

---

## 2. 파일별 역할 및 핵심 로직

### frontend/main.py
- **역할**: 앱 진입점
- **핵심**: `multiprocessing.freeze_support()` 호출 필수 (PyInstaller frozen 앱에서 torch spawn이 앱을 재실행하는 버그 방지)
- `_setup_ffmpeg_path()`: 번들/개발 환경 모두에서 FFmpeg 바이너리 경로 자동 설정

### frontend/main_window.py
- **역할**: 전체 UI 컨트롤러
- **핵심 상태**: `_segments: list[dict]` — 전체 타임라인의 단일 소스
  - 각 segment: `{start: ms, end: ms, keep: bool, text: str}`
- **주요 흐름**:
  - `_start_analysis()` → AIWorker 시작 → `analysis_complete` 시그널 → `_on_analysis_complete()` → `_segments` 설정
  - `_start_stt()` → STTWorker 시작 → `stt_complete` 시그널 → `_on_stt_complete()` → `_segments` 갱신
  - `_start_render()` → RenderWorker 시작 → `render_complete` 시그널
- **설정 로딩**: `_load_settings()` → dict 반환 → Worker 생성 시 전달

### frontend/workers/ai_worker.py
- **역할**: VAD 분석 QThread 래퍼
- **핵심 함수**:
  - `_get_duration_ms()`: ffprobe로 영상 길이 파악
  - `_convert_to_segments(silence_list, duration_ms)`: VAD 무음 목록 → 전체 타임라인 구간 변환
    - silence는 `keep=False`, 발화는 `keep=True`
    - 타임라인 전체(0~duration_ms)를 빈틈 없이 커버 보장
  - `_extract_amplitudes()`: ffmpeg raw PCM → 파형 데이터 (정규화 0~1)

### frontend/workers/stt_worker.py
- **역할**: STT 실행 및 구간 재조립 QThread 래퍼
- **핵심 함수**: `_assign_stt_to_segments(segments, stt_result)`
  - **Timeline Sweep 방식**: cursor를 0부터 max_end까지 이동하며 구간 생성
  - **우선순위**:
    1. STT 구간 내부 → `keep=True, text=문장`
    2. VAD 무음 구간 내부 → `keep=False`
    3. 그 외 GAP → `keep=True, text=""` (Whisper 경계 오차 처리)
  - 최종 0ms 이하 구간 필터링

### frontend/workers/render_worker.py
- **역할**: 최종 렌더링 QThread 래퍼
- `BackendController.run_final_render()` 호출
- 설정: Whisper 모델 크기 적용

### frontend/workers/download_worker.py
- **역할**: URL 다운로드 QThread 래퍼
- 개발 모드: subprocess로 `download_helper.py` 실행 (pyenv python 우선)
- frozen 모드: `yt_dlp` 인프로세스 실행

### backend/export_json.py - `detect_silence()`
- **역할**: Silero VAD로 무음 구간 감지
- **파라미터**:
  - `threshold`: VAD 민감도 (0~1, 기본 0.5, 낮을수록 민감)
  - `min_silence_seconds`: 최소 무음 길이 (이 이하는 발화로 처리)
- **처리 흐름**:
  1. librosa로 오디오 로드 → 16kHz 리샘플
  2. Silero VAD `get_speech_timestamps()` 실행
  3. 발화 타임스탬프에서 역산으로 무음 구간 계산
  4. 100ms 이하 무음 제거 (`if start_sec - current_last_pos > 0.1`)

### backend/backend_controller.py
- **역할**: 백엔드 파이프라인의 단일 진입점
- `run_step1_extract_and_vad()`: 오디오 추출 + VAD
- `run_step2_stt()`: Whisper STT
- `run_final_render()`: 컷편집 + SRT 생성 + 자막 병합
  - **stretch_ratio 보정**: 컷편집 후 실제 영상 길이 ÷ 예상 길이 → 자막 타임코드에 적용

### backend/editor.py
- `create_final_edited_video()`: FFmpeg concat 방식 컷편집
  - 인코딩: `libx264, CRF 18, preset=medium` (시각적 무손실 수준)
- `add_subtitles_to_video()`: SRT 소프트 자막 병합 (`c:v copy` — 무손실)

### backend/transcriber.py
- Stable-Whisper 기반 STT
- `initial_prompt`로 마침표/물음표 스타일 힌트 제공 (느낌표 억제)
- 한국어(`ko`)만 Kiwi 형태소 분석으로 종결어미 감지 후 마침표 추가

---

## 3. 설정 시스템

| 설정 키 | 저장 위치 | 읽는 곳 | 설명 |
|---|---|---|---|
| `min_silence_ms` | QSettings | `_load_settings()` → AIWorker | 최소 무음 길이 (ms) |
| `whisper_model` | QSettings | `_load_settings()` → STTWorker/RenderWorker | Whisper 모델 인덱스 (0~4) |
| `highlight_words` | QSettings | `_get_highlight_words()` | 커스텀 하이라이트 단어 목록 |
| `silence_threshold` | **저장 안됨** | `_load_settings()` → AIWorker | VAD 민감도, 항상 기본값 0.5 사용 |

---

## 4. 발견된 버그 목록

### 🔴 높음 (크래시 가능)

| 위치 | 문제 | 수정 방법 |
|---|---|---|
| `main_window.py:784, 872` | `max(s["end"] for s in self._segments)` — segments 비어있으면 `ValueError` crash | `max(..., default=0)` 추가 |

### 🟡 중간 (기능 오작동)

| 위치 | 문제 | 수정 방법 |
|---|---|---|
| `main_window.py:393-408` | `hasattr(self, "progressBar")` — 실제 위젯명은 `progress_bar` (snake_case). 다운로드 진행률 표시 안됨 | `progressBar` → `progress_bar` 로 변경 |
| `main_window.py:690,695` | `s.value("silence_threshold", 0.5)` — 이 키는 저장된 적 없음. 상태바에 항상 "0.5초" 표시 | `min_silence_ms` 읽어서 초 단위로 변환 |

### 🟢 낮음 (dead code / 미미한 영향)

| 위치 | 문제 | 비고 |
|---|---|---|
| `backend_controller.py:40` | `min_speech_ms=250` 파라미터가 함수 내부에서 사용되지 않음 | Silero VAD 호출 시 누락됨 |
| `main_window.py:911` | `silence_threshold` 키 항상 기본값 0.5 반환 (저장 안함) | UI에서 설정 불가, 고정값으로 동작 |

---

## 5. QThread 안전성

- **시그널/슬롯 패턴**: 모든 Worker는 QThread 서브클래스, UI 업데이트는 시그널로만
- **주의사항**:
  - `viewer.py`의 `plt.show()`는 반드시 메인 스레드에서 실행 (현재 사용 안함)
  - Worker terminate 시 `quit()` + `wait()` 호출 권장 (현재 일부 `terminate()` 직접 호출)
- **multiprocessing**: `freeze_support()` 추가로 frozen 앱에서 spawn 워커 재실행 방지

---

## 6. 알려진 동작 특성

- **STT 후 구간 재조립**: VAD 기반 구간이 STT 결과로 완전히 재구성됨. 이전 VAD 구간 정보는 무음(keep=False)만 2순위로 참조됨
- **stretch_ratio**: FFmpeg concat 후 영상 길이가 미세하게 달라지는 현상 보정. 자막 타임코드에 `× stretch_ratio` 적용
- **자막 병합**: `c:v copy`로 재인코딩 없이 병합 → 영상 화질 보존
- **컷편집**: 재인코딩 필수 (프레임 단위 정밀 컷) → CRF 18로 화질 손실 최소화
