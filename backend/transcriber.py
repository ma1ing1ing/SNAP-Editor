import stable_whisper as ststable
from kiwipiepy import Kiwi
import sys
import os
import json

# 상위 디렉토리를 경로에 추가하여 AI 모듈 임포트
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from AI.main import run_ai_pipeline

def format_time(seconds):
    # 음수가 되지 않도록 처리
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    # SRT 표준 형식인 '00:00:00,000'을 강제합니다.
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"

def transcribe_video_to_srt(video_path, output_srt_path="./backend/Data/subtitle.srt", model_size='small', status_callback=None, progress_callback=None, stopword_mode="default"):

    def emit_status(msg):
        if status_callback:
            status_callback(msg)

    def emit_progress(value):
        if progress_callback:
            progress_callback(value)

    emit_status(f"▶ STT 모델({model_size}) 로드 중...")
    emit_progress(10)
    print(f"\n▶ [STT/자막] stable-ts 정밀 분석 시작: {video_path} (모델: {model_size})")

    model = ststable.load_model(model_size)

    kiwi = Kiwi()

    emit_status("STT 음성 인식 중..")
    emit_progress(30)
    # 음성 인식 및 싱크 보정 실행 (단어별 타임스탬프를 켠 후 재구성해야 정교한 분리/병합이 가능함)
    result = model.transcribe(
        video_path, 
        language=None, 
        word_timestamps=True,
        vad=False # 이중 VAD 방지 (이미 편집된 영상이므로 False가 자연스러움)
    )
    
    # 세그먼트가 너무 길게(또는 짧게) 나오는 것을 방지하기 위해 정교하게 재구성
    result = (
        result
        .split_by_punctuation(['.', '。', '?', '？', '!', '！'])
        .split_by_gap(0.5)
        .merge_by_gap(0.2, max_words=3)
        .split_by_length(max_chars=40, max_words=12)
    )
    
    # stable-ts의 결과 객체에서 언어 정보 가져오기
    detected_lang = result.language
    emit_status(f"▶ 자막 텍스트 보정 중... (언어: {detected_lang})")
    emit_progress(70)
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
    
    # ---------------------------------------------------------
    # STT 결과를 딕셔너리 형태로 변환하여 AI 파이프라인에 전달
    # ---------------------------------------------------------
    # STT 결과를 AI 필터 입력 형식에 맞게 변환한다.
    # segment 전체 정보와 단어별 타임스탬프를 함께 전달한다.
    # ---------------------------------------------------------
    stt_result = {"segments": []}

    for segment in result.segments:
        words_list = []

        if hasattr(segment, "words") and segment.words:
            for w in segment.words:
                words_list.append({
                    "word": w.word,
                    "start": w.start,
                    "end": w.end
                })

        stt_result["segments"].append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": words_list
        })

    print("▶ AI 파이프라인(불용어 탐지) 실행 중...")
    emit_status("▶ AI 불용어 탐지 파이프라인 실행 중...")
    emit_progress(85)
    ai_result = {}
    try:
        # 새로 업데이트된 AI/main.py의 run_ai_pipeline 시그니처에 맞게 호출 수정
        ai_result = run_ai_pipeline(
            video_path=video_path,
            params={
                "mode": stopword_mode,
                "stt_result": stt_result
            }
        )
        
        # 결과를 JSON으로 저장
        ai_output_path = os.path.join(os.path.dirname(output_srt_path), "ai_result.json")
        with open(ai_output_path, "w", encoding="utf-8") as f:
            json.dump(ai_result, f, ensure_ascii=False, indent=2)
            
        # 🌟 원본 타임라인 기반 불용어 데이터를 RenderWorker에서 쓸 수 있도록 캐싱
        backend_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "Data"))
        os.makedirs(backend_data_dir, exist_ok=True)
        cached_ai_path = os.path.join(backend_data_dir, "cached_ai_result.json")
        with open(cached_ai_path, "w", encoding="utf-8") as f:
            json.dump(ai_result, f, ensure_ascii=False, indent=2)
            
        print(f"✅ 불용어 탐지 완료: 총 {len(ai_result.get('cut_points', []))}개의 불용어 구간 발견")
        print(f"✅ AI 결과 저장 완료: {ai_output_path}")
    except Exception as e:
        print(f"❌ AI 파이프라인 실행 중 오류 발생: {e}")

    # main.py와의 호환성을 위해 자막 경로, 감지된 언어, 그리고 파이프라인 연동용 결과값 반환
    return output_srt_path, detected_lang, stt_result, ai_result