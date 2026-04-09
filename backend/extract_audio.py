# 파일명: extractor.py
import ffmpeg
import os

def extract_audio(video_path, output_audio_path):
    print(f"▶ 오디오 추출 시작: {video_path}")
    
    # FFmpeg가 설치된 Homebrew 경로를 환경 변수에 추가합니다 (Apple Silicon Mac 대응)
    homebrew_bin = "/opt/homebrew/bin"
    if os.path.exists(homebrew_bin) and homebrew_bin not in os.environ["PATH"]:
        os.environ["PATH"] += os.pathsep + homebrew_bin

    if not os.path.exists(video_path):
        print(f"❌ 에러: '{video_path}' 파일을 찾을 수 없습니다.")
        return False

    try:
        (
            ffmpeg
            .input(video_path)
            .output(output_audio_path, acodec='pcm_s16le', ac=1, ar='16k')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        print(f"✅ 오디오 추출 완료: {output_audio_path}")
        return True
        
    except ffmpeg.Error as e:
        print("❌ FFmpeg 에러 발생")
        if e.stderr:
            print(e.stderr.decode('utf-8'))
        return False