# 파일명: main.py
# 분리해둔 두 파이썬 파일에서 필요한 함수만 불러옵니다.
from extract_audio import extract_audio
from display_waveform import display_waveform

if __name__ == "__main__":
    # 1. 파일 경로 설정 (여기에 테스트할 영상 이름을 넣으세요)
    INPUT_VIDEO = "./Data/문재인_대통령_퇴임연설.MP4" 
    TEMP_AUDIO = "./Data/temp_audio.wav"

    # 2. extractor.py의 추출 함수 실행
    is_success = extract_audio(INPUT_VIDEO, TEMP_AUDIO)
    
    # 3. 추출이 성공하면 viewer.py의 파형 출력 함수 실행
    if is_success:
        display_waveform(TEMP_AUDIO)