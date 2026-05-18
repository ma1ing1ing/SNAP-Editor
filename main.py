# 파일명: main.py
from extract_audio import extract_audio
from vad_tagger import detect_and_tag_silence
from editor import create_final_edited_audio, create_final_edited_video
import time

if __name__ == "__main__":
    INPUT_VIDEO = "./backend/Data/문재인_대통령_퇴임연설.MP4" 
    TEMP_AUDIO = "./backend/Data/temp_audio.wav"

    # 전체 작업 시작 시간 기록
    start_time = time.time()

    # 1. 영상에서 오디오 추출
    is_success = extract_audio(INPUT_VIDEO, TEMP_AUDIO)
    
    if is_success:
        # 2. 파형 출력 및 무음 구간 리스트 추출
        # (파형 창을 'X' 버튼으로 꺼야 다음 단계로 넘어감)
        silence_list = detect_and_tag_silence(TEMP_AUDIO)
        
        # 3. 최종 편집된 오디오 파일 생성
        create_final_edited_audio(TEMP_AUDIO, silence_list)

        # 4. 최종 결과물: 무음이 잘린 '영상(.mp4)' 렌더링
        # 원본 영상(INPUT_VIDEO)을 넣어야 화면이 같이 잘림
        create_final_edited_video(INPUT_VIDEO, silence_list)

        # 5. 전체 작업 종료 시간 기록 및 소요 시간 계산
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print(f"\n모든 작업 완료, 총 소요 시간: {elapsed_time:.2f}초")