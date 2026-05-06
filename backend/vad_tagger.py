import torch

def detect_and_tag_silence(audio_path, threshold=0.3, min_silence_duration_ms=500, min_speech_duration_ms=250):
    print(f"▶ [VAD 분석] AI 모델을 불러와 목소리를 분석합니다... ({audio_path})")
    
    # 1. Silero VAD 모델 로드 (인터넷에서 한 번만 다운로드 후 로컬에서 캐시로 사용)
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                  model='silero_vad',
                                  force_reload=False,
                                  trust_repo=True)
    (get_speech_timestamps, _, read_audio, _, _) = utils

    # 2. 오디오 파일 읽기 및 분석
    wav = read_audio(audio_path)
    sampling_rate = 16000 # 추출 단계에서 16k로 맞췄으므로 동일하게 설정
    
    # 목소리가 있는 구간 추출 (단위: 오디오 샘플 수)
    speech_timestamps = get_speech_timestamps(
        wav, 
        model, 
        sampling_rate=sampling_rate,
        # 감도 조절 (기본값 0.5 -> 0.3으로 낮춤: 작은 소리도 다 목소리로 잡아냄)
        threshold=threshold, 
        # 최소 무음 길이 (0.5초 이하로 잠깐 숨을 고르는 건 무음으로 자르지 않음)
        min_silence_duration_ms=min_silence_duration_ms, 
        # 최소 목소리 길이 ("헛기침" 같은 짧은 소리를 배제함)
        min_speech_duration_ms=min_speech_duration_ms,
        # 여백(0.2초)
        speech_pad_ms=200
    )
    
    # 3. 무음 구간(Silence) 타임코드 계산
    silence_segments = []
    total_samples = wav.numel() 
    current_pos = 0
    
    for speech in speech_timestamps:
        start_speech = speech['start']
        end_speech = speech['end']
        
        if start_speech > current_pos:
            silence_segments.append({'start': current_pos, 'end': start_speech})
        current_pos = end_speech
        
    # 마지막 음성 이후부터 영상 끝까지의 무음 처리
    if current_pos < total_samples:
        silence_segments.append({'start': current_pos, 'end': total_samples})

    # 샘플 수를 초(Seconds) 단위로 변환
    final_silence_seconds = [{'start': s['start']/sampling_rate, 'end': s['end']/sampling_rate} for s in silence_segments]

    print(f"✅ 최종 무음 구간 개수: {len(final_silence_seconds)}개")

    return final_silence_seconds