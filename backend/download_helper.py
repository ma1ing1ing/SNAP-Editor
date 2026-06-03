"""
Standalone download script — must run with Python 3.10+ (pyenv).
Outputs JSON lines to stdout for progress tracking:
  {"type": "progress", "pct": 50}
  {"type": "done", "path": "/abs/path/to/file.mp4"}
  {"type": "error", "msg": "..."}
"""
import json
import os
import sys

import yt_dlp


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"type": "error", "msg": "usage: download_helper.py <url> <output_dir>"}))
        sys.exit(1)

    url = sys.argv[1]
    output_dir = sys.argv[2]
    os.makedirs(output_dir, exist_ok=True)

    final_path = []

    def _progress_hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                pct = int(d.get("downloaded_bytes", 0) / total * 100)
                print(json.dumps({"type": "progress", "pct": min(pct, 99)}), flush=True)

    def _postprocessor_hook(d):
        # FFmpegMergerPP 완료 시 실제 병합된 파일 경로 캡처
        if d["status"] == "finished":
            path = d.get("info_dict", {}).get("filepath") or d.get("filepath")
            if path:
                final_path.append(path)

    os.environ["PATH"] = "/usr/local/bin:" + os.environ.get("PATH", "")

    ydl_opts = {
        "format": "bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
        "noplaylist": True,
        "merge_output_format": "mp4",
        "cookiesfrombrowser": ("chrome",),
        "js_runtimes": {"node": {"path": "/usr/local/bin/node"}},
        "remote_components": {"ejs:github"},
        "progress_hooks": [_progress_hook],
        "postprocessor_hooks": [_postprocessor_hook],
        "quiet": True,
        "no_warnings": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if final_path:
                final = final_path[-1]
            else:
                # fallback: prepare_filename 기반으로 .mp4 경로 계산
                final = os.path.splitext(ydl.prepare_filename(info))[0] + ".mp4"
            if not os.path.exists(final):
                # 최후 fallback: 가장 최근 .mp4 파일
                mp4s = sorted(
                    [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".mp4")],
                    key=os.path.getmtime,
                )
                if mp4s:
                    final = mp4s[-1]
        print(json.dumps({"type": "done", "path": final}), flush=True)
    except Exception as e:
        print(json.dumps({"type": "error", "msg": str(e)}), flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
