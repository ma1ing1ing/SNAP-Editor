import json
import os
import subprocess
import sys

# PyInstaller 번들 환경 감지
_IS_FROZEN = getattr(sys, "frozen", False)

# 개발 환경: pyenv Python 3.10 우선 사용 (yt-dlp 2026.x + bgutil 호환)
_PYENV_PYTHON = os.path.expanduser("~/.pyenv/versions/3.10.11/bin/python3.10")
_HELPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download_helper.py")


def _download_inprocess(url: str, output_dir: str, progress_callback=None) -> str:
    """yt_dlp를 직접 호출 (frozen 앱 및 개발 fallback용)."""
    import yt_dlp

    final_path = []

    def _progress_hook(d):
        if d["status"] == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                pct = int(d.get("downloaded_bytes", 0) / total * 100)
                progress_callback(min(pct, 99))

    def _postprocessor_hook(d):
        if d["status"] == "finished":
            path = d.get("info_dict", {}).get("filepath") or d.get("filepath")
            if path:
                final_path.append(path)

    base_opts = {
        "format": "bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "extractor_args": {"youtube": {"player_client": ["android", "web_embedded"]}},
        "progress_hooks": [_progress_hook],
        "postprocessor_hooks": [_postprocessor_hook],
        "quiet": True,
        "no_warnings": True,
    }

    browsers = ["safari", "chrome", "firefox", None]
    last_err = None
    info = None
    for browser in browsers:
        ydl_opts = dict(base_opts)
        if browser:
            ydl_opts["cookiesfrombrowser"] = (browser,)
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if final_path:
                    final = final_path[-1]
                else:
                    final = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp4"
                if not os.path.exists(final):
                    mp4s = sorted(
                        [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".mp4")],
                        key=os.path.getmtime,
                    )
                    final = mp4s[-1] if mp4s else final
            break
        except Exception as e:
            last_err = e
            final_path.clear()
            continue
    else:
        raise RuntimeError(str(last_err))

    if progress_callback:
        progress_callback(100)
    return final


def download_video(url: str, output_dir: str, progress_callback=None) -> str:
    os.makedirs(output_dir, exist_ok=True)

    if _IS_FROZEN:
        return _download_inprocess(url, output_dir, progress_callback)

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
