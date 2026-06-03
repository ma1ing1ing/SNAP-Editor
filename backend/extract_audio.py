# 파일명: extractor.py
import ffmpeg
import os

def extract_audio(video_path, output_audio_path):
    # 이미 추출된 오디오 파일이 존재하는지 확인.
    if os.path.exists(output_audio_path):
        print(f"이미 추출된 오디오 파일이 존재하여 추출 과정을 건너뜁니다. ({output_audio_path})")
        return True # 바로 다음 단계로 진행

    print(f"▶ 오디오 추출 시작: {video_path}")
    
    if not os.path.exists(video_path):
        print(f"❌ 에러: '{video_path}' 파일을 찾을 수 없습니다.")
        return False

    try:
        (
            ffmpeg
            .input(video_path)
            .output(
                output_audio_path,
                acodec='pcm_s16le', # Whisper/stable-ts 권장 포맷
                ac=1,               # 모노 채널로 통합 (연산 효율 증대)
                ar='16k',           # 16000Hz 샘플링 레이트 고정
                map_metadata='-1',  # 불필요한 메타데이터 제거 (오류 방지)
                # 🌟 싱크 밀림 방지를 위한 핵심 옵션: 오디오 타임스탬프 강제 정렬
                af='aresample=async=1:min_hard_comp=0.100000:first_pts=0'
            )
            .overwrite_output()     
            .run(capture_stdout=True, capture_stderr=True)
        )
        print(f"오디오 추출 완료: {output_audio_path}")
        return True
        
    except ffmpeg.Error as e:
        print("❌ FFmpeg 에러 발생")
        print(e.stderr.decode('utf-8'))
        return False
