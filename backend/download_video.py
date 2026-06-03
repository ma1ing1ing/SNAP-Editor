import os
import yt_dlp


def download_video(url: str, output_dir: str, progress_callback=None) -> str:
    """
    yt-dlp로 url을 다운로드하고 저장된 파일 경로를 반환한다.
    progress_callback(int): 0~100 진행률
    """
    os.makedirs(output_dir, exist_ok=True)
    downloaded_path = []

    def _progress_hook(d):
        if d["status"] == "downloading" and progress_callback:
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                pct = int(d.get("downloaded_bytes", 0) / total * 100)
                progress_callback(min(pct, 99))
        elif d["status"] == "finished":
            downloaded_path.append(d["filename"])

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "cookiesfrombrowser": ("chrome",),
        "extractor_args": {"youtube": {"player_client": ["tv_embedded", "web"]}},
        "progress_hooks": [_progress_hook],
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # merge 후 최종 경로
        final = ydl.prepare_filename(info)
        if not final.endswith(".mp4"):
            final = os.path.splitext(final)[0] + ".mp4"

    if progress_callback:
        progress_callback(100)

    return final


if __name__ == "__main__":
    _url = "https://www.youtube.com/watch?v=QsYBgJgkd0E&t=155s"
    _out = os.path.join(os.path.dirname(__file__), "Data")
    path = download_video(_url, _out, progress_callback=lambda p: print(f"다운로드 {p}%"))
    print(f"저장 완료: {path}")
