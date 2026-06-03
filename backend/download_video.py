import json
import os
import subprocess
import sys

# PyInstaller 번들 환경 감지
_IS_FROZEN = getattr(sys, "frozen", False)

# 개발 환경: pyenv Python 3.10 우선 사용 (yt-dlp 2026.x + bgutil 호환)
_PYENV_PYTHON = os.path.expanduser("~/.pyenv/versions/3.10.11/bin/python3.10")
_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_helper.py")


def download_video(url: str, output_dir: str, progress_callback=None) -> str:
    if _IS_FROZEN:
        raise RuntimeError(
            "URL 다운로드는 현재 배포 버전에서 지원되지 않습니다.\n"
            "로컬 mp4 파일을 직접 열어 사용해주세요."
        )

    os.makedirs(output_dir, exist_ok=True)

    python = _PYENV_PYTHON if os.path.isfile(_PYENV_PYTHON) else sys.executable
    proc = subprocess.Popen(
        [python, _HELPER, url, output_dir],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )

    result_path = None
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        if msg["type"] == "progress" and progress_callback:
            progress_callback(msg["pct"])
        elif msg["type"] == "done":
            result_path = msg["path"]
        elif msg["type"] == "error":
            proc.wait()
            raise RuntimeError(msg["msg"])

    proc.wait()
    if proc.returncode != 0 and result_path is None:
        raise RuntimeError("다운로드 실패 (알 수 없는 오류)")

    if progress_callback:
        progress_callback(100)

    return result_path


if __name__ == "__main__":
    _url = "https://www.youtube.com/watch?v=QsYBgJgkd0E&t=155s"
    _out = os.path.join(os.path.dirname(__file__), "Data")
    path = download_video(_url, _out, progress_callback=lambda p: print(f"다운로드 {p}%"))
    print(f"저장 완료: {path}")
