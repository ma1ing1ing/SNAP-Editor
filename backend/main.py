import time
from extract_audio import extract_audio
from vad_tagger import detect_and_tag_silence
from viewer import display_waveform_with_silence
from editor import create_final_edited_video, add_subtitles_to_video
from transcriber import transcribe_video_to_srt

if __name__ == "__main__":
    # ==========================================
    # 1. 파일 경로 설정
    # 2시간 영상 기준 약 11분 소요
    # ==========================================
    INPUT_VIDEO = "./backend/Data/문재인_대통령_퇴임연설_2시간.mp4" 
    TEMP_AUDIO = "./backend/Data/temp_audio.wav"
    EDITED_VIDEO = "./backend/Data/edited_video.mp4" 
    SUBTITLE_SRT = "./backend/Data/subtitle.srt"    
    FINAL_RESULT = "./backend/Data/final_result.mp4" 

    # ==========================================
    # 2. 메인 파이프라인 실행
    # ==========================================
    print("자동 편집 및 자막 생성 프로세스 시작")
    
    # 1단계: 원본 영상에서 오디오만 추출 (싱크 최적화)
    if extract_audio(INPUT_VIDEO, TEMP_AUDIO):
        
        start_time = time.time()
        
        # 2단계: AI 기반 무음 구간 탐지 및 리스트화
        silence_list = detect_and_tag_silence(TEMP_AUDIO)
        
        # 3단계: 무음구간 태깅 오디오 파형 창 출력
        display_waveform_with_silence(TEMP_AUDIO, silence_segments=silence_list)
        
        # 4단계: 추출된 리스트를 바탕으로 컷편집 영상 생성
        create_final_edited_video(INPUT_VIDEO, silence_list, EDITED_VIDEO)
        
        # 5단계: 편집된 영상의 오디오를 분석하여 정밀 자막(SRT) 생성
        srt_path, detected_lang = transcribe_video_to_srt(EDITED_VIDEO, SUBTITLE_SRT)
        
        # 6단계: 영상과 자막을 합쳐 최종 결과물(MP4) 도출
        add_subtitles_to_video(EDITED_VIDEO, srt_path, FINAL_RESULT, language=detected_lang)
        
        end_time = time.time()
        
        # 결과 리포트
        print("\n" + "="*40)
        print(f"🎉 모든 작업이 성공적으로 완료되었습니다!")
        print(f"▶ 최종 결과물: {FINAL_RESULT}")
        print(f"▶ 대기 시간을 포함한 총 구동 시간: {end_time - start_time:.2f}초")
        print("="*40)
    else:
        print("❌ 오디오 추출에 실패하여 프로세스를 중단합니다.")