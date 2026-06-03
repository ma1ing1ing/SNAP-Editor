# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SNAP-Editor** (Smart, Neat, Automated Processing) is an automated video editing application that removes silence from videos and generates precise subtitles. It consists of three main components:

- **Frontend**: PyQt6-based desktop GUI for video selection, playback, analysis visualization, and subtitle editing
- **Backend**: Core automation pipeline handling audio extraction, voice activity detection (VAD), video cutting, and subtitle generation
- **AI Module**: NLP-based filtering and metadata analysis using the Kiwi morphological analyzer

## Architecture

### High-Level Pipeline

The backend operates as a sequential 4-step pipeline (managed by `BackendController`):

1. **Step 1 (Extract & VAD)**: Audio extraction from video → Voice Activity Detection using Silero VAD model → JSON export of silence segments
2. **Step 2 (Visualization)**: Display waveform with detected silence segments for user approval
3. **Step 3 (Render)**: Cut video based on approved silence segments using FFmpeg, output edited video
4. **Step 4 (STT & Subtitles)**: Transcribe audio using Faster-Whisper → Generate SRT subtitles with Kiwi-based Korean punctuation correction → Merge subtitles into final video

### Key Design Patterns

**Frontend-Backend Separation**: 
- `BackendController` in `backend/backend_controller.py` provides a modular interface with progress/log callbacks for PyQt6 integration
- `AIWorker` (QThread) in `frontend/workers/ai_worker.py` runs backend tasks asynchronously without blocking the GUI

**Audio Sync Preservation**:
- Audio extraction uses FFmpeg's `aresample=async=1` filter to prevent timestamp drift
- Video rendering uses CFR (Constant Frame Rate) enforcement and `.ts` intermediate format to avoid sync drift during concatenation
- All audio is normalized to 16kHz mono for consistency across VAD and STT models

**State Management**:
- Silence segments and metadata stored in JSON files between pipeline steps
- Allows frontend to pause/resume workflow and persist analysis results

## File Structure

```
backend/
├── main.py                  # Direct pipeline execution (testing/CLI)
├── backend_controller.py    # Modular interface for frontend integration
├── extract_audio.py         # FFmpeg-based audio extraction + sync optimization
├── vad_tagger.py           # Silero VAD model inference → silence detection
├── editor.py               # FFmpeg-based video cutting and subtitle merging
├── transcriber.py          # Faster-Whisper STT + Kiwi-based Korean punctuation
├── viewer.py               # Matplotlib-based waveform visualization
├── export_json.py          # VAD result serialization
├── download_video.py       # YouTube downloader (testing utility)
└── Data/                   # Working directory for temporary files and outputs

frontend/
├── main.py                 # Qt application entry point
├── main_window.py          # Main window controller (file selection, playback, analysis UI)
├── main_window.ui          # UI layout (Qt Designer XML)
├── video_player.py         # QMediaPlayer wrapper with position tracking
├── settings_dialog.py      # Settings persistence (silence threshold, model size)
├── workers/
│   └── ai_worker.py        # QThread wrapper for backend_controller
├── utils/
│   └── time_formatter.py   # Timestamp formatting utilities
└── *.ui files              # Additional dialog layouts

AI/
├── main.py                 # Kiwi morphological analysis (future enhancement)
└── stopwords_ko.json       # Korean stop word dictionary
```

## Development Commands

### Running the Application

```bash
# Start frontend GUI
cd frontend
python main.py

# Run backend pipeline directly (testing/CLI mode)
cd backend
python main.py
```

### Dependencies

Key libraries (from `backend/Library.txt`):
- **Audio/Video**: `ffmpeg-python`, FFmpeg system binary
- **VAD**: `silero-vad` (torch-based)
- **STT**: `faster-whisper`, `stable-whisper` (Whisper-based)
- **Korean NLP**: `kiwipiepy` (morphological analysis)
- **Frontend**: `PyQt6`
- **Audio Processing**: `librosa`, `torch`

Install via pip (no `requirements.txt` currently; manual setup needed):
```bash
pip install PyQt6 ffmpeg-python torch librosa stable-ts faster-whisper kiwipiepy
```

Ensure FFmpeg system binary is installed:
```bash
# macOS
brew install ffmpeg
```

### Testing & Utilities

```bash
# Download test video from YouTube
python backend/download_video.py

# Test video cutting on a specific segment
python backend/test_cut.py

# Export VAD analysis results as JSON
python backend/export_json.py
```

## Important Implementation Details

### Video Sync Preservation

When modifying video editing logic in `editor.py`:
- Use `.ts` (MPEG-TS) intermediate format for clip concatenation (preserves frame timestamps better than `.mp4`)
- Always enforce CFR with FFmpeg flags like `-vf "fps=fps=30"` on output
- Include `-copyts` to preserve timestamps and `-muxdelay 0` to prevent drift

### Audio Processing in VAD

In `vad_tagger.py`, the threshold parameter (default 0.3) controls sensitivity:
- Lower threshold (0.2-0.3): Detects quieter speech
- Higher threshold (0.5+): Only captures loud speech
- Test changes with `viewer.py` visualization before committing

### Korean Subtitle Generation

In `transcriber.py`, Kiwi punctuation logic only runs for `detected_lang == 'ko'`. If adding support for other languages, extend the conditional but avoid modifying the Kiwi tokenization path for non-Korean languages.

### Frontend-Backend Threading

⚠️ **Critical**: The `viewer.py` waveform display (`plt.show()`) must run on the **main thread** when integrated with PyQt6, not in `AIWorker` threads. See `backend_controller.py` Step 2 comments.

## Known Issues & Gotchas

1. **Matplotlib on macOS**: If viewer crashes when called from `AIWorker`, move visualization to main thread only
2. **Module imports**: Backend uses relative imports; ensure `sys.path` adjustments in controller when calling from frontend
3. **Temp file cleanup**: `Data/temp_clips/` directory created by `editor.py` is not auto-cleaned; consider adding cleanup logic if debugging
4. **Model downloads**: First run of VAD/Whisper/Kiwi downloads models (~1GB total); requires internet and takes ~5-10 minutes

## UI State

Frontend is partially implemented:
- ✅ Main window layout, file selection, video playback controls, settings dialog
- ⚠️ Analysis pipeline integration: `AIWorker.run()` has TODO comment; backend_controller not yet called
- ⚠️ Subtitle timeline visualization and inline editing not fully connected
- ⚠️ Real-time progress bar and status updates need backend signal routing

When implementing signal connections, ensure `BackendController` callbacks (`progress_callback`, `log_callback`) route to Qt signals in `AIWorker` for thread-safe updates.

## Git Workflow Notes

Local settings in `.claude/settings.local.json` allow Python and git commands. When making changes:
- Commit often with clear messages (recent commits follow pattern: `feat:`, `refactor:`, `chore:`)
- Backend changes typically affect the pipeline steps; frontend changes often touch Qt signal routing
- No pre-commit hooks configured; manual testing advised before pushing

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).


