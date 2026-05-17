import stable_whisper as ststable
from kiwipiepy import Kiwi

def format_time(seconds):
    # 음수가 되지 않도록 처리
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    # SRT 표준 형식인 '00:00:00,000'을 강제합니다.
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def transcribe_video_to_srt(video_path, output_srt_path="./backend/Data/subtitle.srt", model_size='small'):
    print(f"\n▶ [STT/자막] stable-ts 정밀 분석 시작: {video_path}")
    
    # 🌟 최신 환경에 맞춰 복잡한 예외처리 없이 깔끔하게 모델 로드
    # (맥북 성능을 믿고 기본 설정으로 로드합니다)
    model = ststable.load_model(model_size) 

    kiwi = Kiwi()

    # 음성 인식 및 싱크 보정 실행
    result = model.transcribe(
        video_path, 
        language=None, 
        word_timestamps=True,
        vad=False # 이중 VAD 방지 (이미 편집된 영상이므로 False가 자연스러움)
    )
    
    # stable-ts의 결과 객체에서 언어 정보 가져오기
    detected_lang = result.language
    print(f"▶ 감지된 언어: {detected_lang}")

    # 결과 데이터를 SRT 형식으로 가공 및 한국어 문장 부호 보정
    with open(output_srt_path, "w", encoding="utf-8") as srt_file:
        for i, segment in enumerate(result.segments, start=1):
            text = segment.text.strip()
            if not text:
                continue
            
            # 한국어일 경우에만 마침표 보정 로직 실행
            if detected_lang == 'ko' and not text.endswith(('.', '?', '!')):
                tokens = kiwi.tokenize(text)
                if tokens:
                    last_tag = tokens[-1].tag
                    # 어미(EF)로 끝나거나 특정 글자로 끝나면 마침표 추가
                    if last_tag.startswith('EF') or text[-1] in ['다', '요', '까', '죠']:
                        text += "."
            
            start_time = format_time(segment.start)
            end_time = format_time(segment.end)
            
            srt_file.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")

    print(f"✅ 정밀 자막 파일 생성 완료: {output_srt_path}")
    
    # main.py와의 호환성을 위해 자막 경로와 감지된 언어 반환
    return output_srt_path, detected_lang