# -*- mode: python ; coding: utf-8 -*-
"""
SNAP-Editor PyInstaller spec
macOS ARM64 (Apple Silicon) 타겟

빌드 전 준비사항:
  1. bin/ffmpeg, bin/ffprobe 정적 빌드 배치
     https://evermeet.cx/ffmpeg/ 에서 macOS ARM64 버전 다운로드
  2. venv 활성화: source venv/bin/activate
  3. 빌드: pyinstaller SNAP-Editor.spec

결과물: dist/SNAP-Editor.app
"""

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

project_root = os.path.abspath(".")
frontend_dir = os.path.join(project_root, "frontend")
backend_dir  = os.path.join(project_root, "backend")
bin_dir      = os.path.join(project_root, "bin")

# ── 포함할 데이터 파일 ──────────────────────────────────────────────────────
datas = [
    # UI 파일
    (os.path.join(frontend_dir, "main_window.ui"),        "."),
    (os.path.join(frontend_dir, "settings_dialog.ui"),    "."),
    (os.path.join(frontend_dir, "analysis_popup.ui"),     "."),
    (os.path.join(frontend_dir, "alert_popup.ui"),        "."),
    (os.path.join(frontend_dir, "error_dialog.ui"),       "."),
    (os.path.join(frontend_dir, "render_complete_popup.ui"), "."),

    # 아이콘
    (os.path.join(frontend_dir, "icons"), "icons"),

    # 백엔드 Python 소스 (모듈로 import되므로 datas 포함)
    (os.path.join(backend_dir, "backend_controller.py"), "backend"),
    (os.path.join(backend_dir, "extract_audio.py"),      "backend"),
    (os.path.join(backend_dir, "vad_tagger.py"),         "backend"),
    (os.path.join(backend_dir, "editor.py"),             "backend"),
    (os.path.join(backend_dir, "transcriber.py"),        "backend"),
    (os.path.join(backend_dir, "export_json.py"),        "backend"),
    (os.path.join(backend_dir, "download_video.py"),     "backend"),
    (os.path.join(backend_dir, "download_helper.py"),    "backend"),

    # kiwipiepy 모델 데이터
    *collect_data_files("kiwipiepy_model"),
    *collect_data_files("kiwipiepy"),

    # stable_whisper / whisper 데이터
    *collect_data_files("whisper"),
    *collect_data_files("stable_whisper"),
]

# bin/ FFmpeg 바이너리 (존재할 때만 포함)
if os.path.isfile(os.path.join(bin_dir, "ffmpeg")):
    datas.append((os.path.join(bin_dir, "ffmpeg"),  "bin"))
if os.path.isfile(os.path.join(bin_dir, "ffprobe")):
    datas.append((os.path.join(bin_dir, "ffprobe"), "bin"))

# ── Hidden imports ──────────────────────────────────────────────────────────
hiddenimports = [
    # PyQt6
    "PyQt6.QtCore",
    "PyQt6.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtMultimedia",
    "PyQt6.QtMultimediaWidgets",
    "PyQt6.uic",
    "PyQt6.sip",

    # torch / torchaudio
    "torch",
    "torch.nn",
    "torchaudio",
    "torchaudio.transforms",

    # Whisper / stable_whisper
    "stable_whisper",
    "whisper",
    "whisper.audio",
    "whisper.model",
    "whisper.tokenizer",

    # Korean NLP
    "kiwipiepy",
    "kiwipiepy_model",

    # Audio / ML
    "librosa",
    "librosa.core",
    "librosa.feature",
    "soundfile",
    "scipy",
    "scipy.signal",
    "numpy",
    "numba",
    "sklearn",

    # 기타
    "ffmpeg",
    "yt_dlp",
    "matplotlib",
    "matplotlib.backends.backend_agg",
]

# ── 제외할 모듈 (앱 크기 절감) ─────────────────────────────────────────────
excludes = [
    "tkinter",
    "unittest",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
]

# ── Analysis ────────────────────────────────────────────────────────────────
a = Analysis(
    [os.path.join(frontend_dir, "main.py")],
    pathex=[frontend_dir, backend_dir],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SNAP-Editor",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=os.path.join(frontend_dir, "icons", "app.png"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="SNAP-Editor",
)

app = BUNDLE(
    coll,
    name="SNAP-Editor.app",
    icon=os.path.join(frontend_dir, "icons", "app.png"),
    bundle_identifier="com.snap.editor",
    info_plist={
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1",
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "음성 분석을 위해 마이크 접근이 필요합니다.",
        "LSMinimumSystemVersion": "12.0",
    },
)
