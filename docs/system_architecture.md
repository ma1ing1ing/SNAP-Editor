# SNAP-Editor 시스템 구성도

> **S**mart **N**eat **A**utomated **P**rocessing — 영상에서 무음 구간을 자동 제거하고 정밀 자막을 생성하는 AI 비디오 편집 도구

---

## 📋 사용 시나리오 흐름

사용자가 영상을 입력하고 최종 편집본을 얻기까지의 전체 흐름.  
각 단계에서 실제로 호출되는 컴포넌트와 핵심 처리를 함께 표시.

```mermaid
flowchart TD
    %% ── 입력 ──────────────────────────────────────────
    U_FILE([🗂 로컬 파일 선택\nMainWindow._open_file])
    U_URL([🔗 URL 붙여넣기\nMainWindow._open_url])

    %% ── Step 0: 다운로드 ──────────────────────────────
    S0[⬇ Step 0 · 영상 다운로드\nDownloadWorker\ndownload_video · yt-dlp]

    %% ── 영상 준비 ─────────────────────────────────────
    V_READY[(🎬 입력 영상\n.mp4 / .mov)]

    %% ── Step 1: 오디오 추출 + VAD ─────────────────────
    S1[🔊 Step 1 · 오디오 추출 + 무음 감지\nAIWorker → BackendController\nextract_audio · detect_silence\nSilero VAD]
    A_WAV[(🎵 audio.wav\n16kHz 모노)]
    A_JSON[(📄 silence.json\n무음 구간 좌표)]

    %% ── Step 2: STT 자막 생성 ─────────────────────────
    S2[🗣 Step 2 · 음성 인식 · 자막 생성\nSTTWorker → BackendController\ntranscribe_video_to_srt\n_assign_stt_to_segments]
    AI_WHISPER{{🤖 stable-whisper\nKorean STT}}
    A_SRT[(📝 subtitle.srt\n참고용 자막 파일)]
    A_SEG[(📦 segments v2\nkeep·text·start·end)]

    %% ── 편집 ──────────────────────────────────────────
    U_EDIT([✏️ 구간 편집 · 자막 수정\nMainWindow\nlist_segments 테이블])

    %% ── Step 3: 렌더링 ────────────────────────────────
    S3[🎞 Step 3 · 최종 렌더링\nRenderWorker → BackendController\ncreate_final_edited_video\nadd_subtitles_to_video\nSRT 재생성 + stretch_ratio 싱크 보정]
    AI_FFMPEG{{⚙ FFmpeg\nH.264 인코딩}}

    %% ── 출력 ──────────────────────────────────────────
    OUT_MP4[(🎉 final_edited.mp4\n무음 제거 + 소프트 자막 트랙 병합)]

    %% ── 흐름 연결 ─────────────────────────────────────
    U_FILE --> V_READY
    U_URL  --> S0 --> V_READY

    V_READY --> S1
    S1 --> A_WAV & A_JSON

    A_WAV & A_JSON --> S2
    V_READY -.->|원본 영상 직접 참조| S2
    S2 --> AI_WHISPER
    AI_WHISPER --> A_SRT & A_SEG

    A_SEG --> U_EDIT

    U_EDIT -->|편집된 segments| S3
    S3 --> AI_FFMPEG
    AI_FFMPEG --> OUT_MP4

    %% ── 스타일 ────────────────────────────────────────
    classDef userAction  fill:#E3F2FD,stroke:#1565C0,color:#0D47A1,rx:20
    classDef pipeline    fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef artifact    fill:#F5F5F5,stroke:#757575,color:#424242
    classDef aiModel     fill:#FFF8E1,stroke:#F9A825,color:#795548

    class U_FILE,U_URL,U_EDIT userAction
    class S0,S1,S2,S3 pipeline
    class V_READY,A_WAV,A_JSON,A_SRT,A_SEG,OUT_MP4 artifact
    class AI_WHISPER,AI_FFMPEG aiModel
```

---

## 🏗 컴포넌트 레이어 구조

시스템을 4개 레이어로 분리하여 각 컴포넌트의 역할과 레이어 간 인터페이스를 표시.

```mermaid
flowchart LR
    %% ── Frontend 레이어 ───────────────────────────────
    subgraph FE ["🖥  Frontend  ·  PyQt6"]
        MW["MainWindow\n파일 선택 · 구간 편집 · 상태 표시"]
        VP["VideoPlayer\n영상 미리보기 · 재생 제어"]
        WW["WaveformWidget\n파형 시각화 · 무음 구간 색상"]
        SD["SettingsDialog\nVAD 감도 · Whisper 모델 설정"]
        MW --- VP & WW & SD
    end

    %% ── Workers 레이어 ────────────────────────────────
    subgraph WK ["⚙  Workers  ·  QThread 비동기"]
        DW["DownloadWorker\nURL → MP4 다운로드"]
        AW["AIWorker\nStep 1 실행\n진폭 추출 → 파형 신호"]
        SW["STTWorker\nStep 2 실행\n_assign_stt_to_segments"]
        RW["RenderWorker\nStep 3 실행\n통계 업데이트"]
    end

    %% ── BackendController 레이어 ──────────────────────
    subgraph BC ["🎛  BackendController  ·  파이프라인 조율"]
        BC1["run_step1_extract_and_vad\n오디오 추출 + VAD 무음 감지"]
        BC2["run_step2_stt\nSTT 호출 + SRT 생성"]
        BC3["run_final_render\n무음 제거 + 자막 병합"]
        BC1 --> BC2 --> BC3
    end

    %% ── Backend 레이어 ────────────────────────────────
    subgraph BE ["🔧  Backend Modules"]
        EA["extract_audio\nFFmpeg → 16kHz WAV"]
        DS["detect_silence\nSilero VAD → silence.json"]
        TR["transcriber\nstable-whisper → .srt"]
        ED["editor\nFFmpeg → MP4 + 자막 트랙"]
        DV["download_video\nyt-dlp + 쿠키 Fallback"]
    end

    %% ── 레이어 간 인터페이스 ──────────────────────────
    MW  -->|"pyqtSignal\n(start/stop)"| DW & AW & SW & RW
    DW  -->|"download_complete\n(path)"| MW
    AW  -->|"waveform_ready\nanalysis_complete"| MW
    SW  -->|"stt_complete\n(segments)"| MW
    RW  -->|"render_complete\n(path, segments)"| MW

    AW  -->|"progress/log callback"| BC1
    SW  -->|"progress/log callback"| BC2
    RW  -->|"progress/log callback"| BC3
    DW  --> DV

    BC1 --> EA & DS
    BC2 --> TR
    BC3 --> ED

    %% ── 스타일 ────────────────────────────────────────
    classDef feStyle  fill:#E3F2FD,stroke:#1565C0,color:#0D47A1
    classDef wkStyle  fill:#F3E5F5,stroke:#6A1B9A,color:#4A148C
    classDef bcStyle  fill:#E8F5E9,stroke:#2E7D32,color:#1B5E20
    classDef beStyle  fill:#FFF8E1,stroke:#F9A825,color:#795548

    class MW,VP,WW,SD feStyle
    class DW,AW,SW,RW wkStyle
    class BC1,BC2,BC3 bcStyle
    class EA,DS,TR,ED,DV beStyle
```

---

## 📦 데이터 상태 변화

`segments` 객체가 각 파이프라인 단계를 거치며 어떻게 변화하는지 추적.

```mermaid
flowchart LR
    %% ── 원본 ──────────────────────────────────────────
    RAW[(🎬 원본 영상\n.mp4)]

    %% ── Step 1 산출 ───────────────────────────────────
    WAV[(🎵 audio.wav\n16kHz · 모노)]
    SEG1["📦 segments v1\nstart·end ms\nkeep True/False\ntext: 비어있음"]

    %% ── Step 2 산출 ───────────────────────────────────
    SEG2["📦 segments v2\nstart·end ms\nkeep True/False\ntext: STT 결과 채워짐\nwords: 단어별 타임스탬프"]

    %% ── 사용자 편집 ───────────────────────────────────
    SEG3["📦 segments v3\nstart·end ms  ← 수정 가능\nkeep True/False  ← 토글 가능\ntext: 수동 교정 가능"]

    %% ── 렌더링 입력 ───────────────────────────────────
    SILENCE["🔇 silence_segments\nkeep=False 구간만 추출\n단위: 초 변환"]

    %% ── 최종 출력 ─────────────────────────────────────
    FINAL[(🎉 final_edited.mp4\n소프트 자막 트랙 포함\n(mov_text 포맷))]

    %% ── 흐름 ──────────────────────────────────────────
    RAW -->|"extract_audio\n+detect_silence"| WAV
    WAV -->|"_convert_to_segments\nms 단위 교차 배치"| SEG1
    SEG1 -->|"transcribe_video_to_srt\n_assign_stt_to_segments"| SEG2
    SEG2 -->|"사용자 keep 토글\n자막 텍스트 수정"| SEG3
    SEG3 -->|"keep=False 필터링\n초 단위 변환"| SILENCE
    SILENCE -->|"create_final_edited_video\nadd_subtitles_to_video\n+ stretch_ratio 싱크 보정"| FINAL

    %% ── 스타일 ────────────────────────────────────────
    classDef fileNode fill:#F5F5F5,stroke:#757575,color:#424242
    classDef segNode  fill:#E8EAF6,stroke:#3949AB,color:#1A237E
    classDef userNode fill:#E3F2FD,stroke:#1565C0,color:#0D47A1,rx:10

    class RAW,WAV,FINAL fileNode
    class SEG1,SEG2,SILENCE segNode
    class SEG3 userNode
```

> **segments 핵심 필드**
>
> | 필드 | 타입 | 설명 |
> |---|---|---|
> | `start` | int (ms) | 구간 시작 시각 |
> | `end` | int (ms) | 구간 종료 시각 |
> | `keep` | bool | `True` = 보존(초록), `False` = 제거(빨강) |
> | `text` | str | STT 자막 텍스트 (Step 2 이후 채워짐) |
> | `words` | list | 단어별 타임스탬프 (불용어 강조에 사용) |

---

## ⚙ 기술 스택

| 레이어 | 기술 | 버전/비고 |
|---|---|---|
| **GUI** | PyQt6 | QMainWindow · QThread · pyqtSignal |
| **음성 인식 (STT)** | stable-whisper | Whisper 기반, 한국어 word timestamps |
| **무음 감지 (VAD)** | Silero VAD | torch.hub, 감도 0.0–1.0 조절 가능 |
| **영상 처리** | FFmpeg + ffmpeg-python | H.264 CRF 인코딩, 소프트 자막 트랙 |
| **다운로드** | yt-dlp | YouTube 403 우회 (android client + 쿠키 fallback) |
| **오디오 분석** | librosa · torchaudio | 16kHz 리샘플, RMS 진폭 추출 |
| **배포** | PyInstaller + static-ffmpeg | macOS .app 번들, frozen 환경 대응 |
