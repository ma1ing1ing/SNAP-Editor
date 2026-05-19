# 파일명: vad_tagger.py
import torch
import torchaudio
import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np

def detect_and_tag_silence(audio_path):
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
    # vad_tagger.py 수정
    speech_timestamps = get_speech_timestamps(
        wav, 
        model, 
        sampling_rate=sampling_rate,
        
        # 1. 감도 조절 (기본값 0.5 -> 0.3으로 낮춤)
        # 값이 낮을수록 더 예민해져서 작은 소리도 다 목소리로 잡아냅니다.
        threshold=0.3, 
        
        # 2. 최소 무음 길이 (예: 500ms = 0.5초)
        # 말하다가 0.5초 이하로 잠깐 숨을 고르는 건 무음으로 자르지 말고 하나의 말로 이어붙이라는 뜻입니다.
        min_silence_duration_ms=500, 
        
        # 3. 최소 목소리 길이 (예: 250ms = 0.25초)
        # "헛기침"이나 "마이크 툭 치는 소리" 같은 아주 짧은 소리를 목소리로 착각하지 않게 막아줍니다.
        min_speech_duration_ms=250   
    )
    
    # 3. 1차 무음 구간(Silence) 타임코드 계산 (VAD 기준)
    silence_segments = []
    total_samples = wav.numel() 
    current_pos = 0
    
    for speech in speech_timestamps:
        start_speech = speech['start']
        end_speech = speech['end']
        
        if start_speech > current_pos:
            silence_segments.append({'start': current_pos, 'end': start_speech})
        current_pos = end_speech
        
    if current_pos < total_samples:
        silence_segments.append({'start': current_pos, 'end': total_samples})

    # 샘플 수를 초(Seconds) 단위로 변환 (1차 후보군)
    silence_seconds = [{'start': s['start']/sampling_rate, 'end': s['end']/sampling_rate} for s in silence_segments]

    # ==========================================
    # 4. 음량(RMS) 기반 2차 필터링
    # ==========================================
    print("▶ [음량 분석] VAD가 찾은 무음 구간 중, 실제 소리(박수 등)가 큰 구간을 걸러냅니다...")
    y, sr_librosa = librosa.load(audio_path, sr=None)
    
    # 소리의 크기(에너지)를 프레임 단위로 계산합니다.
    rms = librosa.feature.rms(y=y)[0] 
    frames_per_sec = sr_librosa / 512 # librosa의 기본 hop_length
    
    final_silence_seconds = []
    
    for sil in silence_seconds:
        start_frame = int(sil['start'] * frames_per_sec)
        end_frame = int(sil['end'] * frames_per_sec)
        
        # 해당 구간의 평균 소리 크기 계산
        segment_rms = np.mean(rms[start_frame:end_frame])
        
        # 💡 볼륨 임계치 설정 (이 숫자를 조절해 '박수 소리'와 '숨소리'를 구분합니다)
        # 0.02 정도면 아주 조용한 백색소음 수준입니다. 이보다 크면 무언가 소리(박수)가 있다고 판단!
        if segment_rms < 0.02: 
            final_silence_seconds.append(sil)
        else:
            print(f"  - 🚫 제외됨: {sil['start']:.2f}초 ~ {sil['end']:.2f}초 (소리 크기가 커서 보존합니다. RMS: {segment_rms:.4f})")

    print(f"✅ 최종 확정된 진짜 무음 구간 개수: {len(final_silence_seconds)}개")

    # ==========================================
    # 5. 시각화 (파형 + 최종 무음 태깅)
    # ==========================================
    plt.figure(figsize=(14, 5))
    librosa.display.waveshow(y, sr=sr_librosa, color='blue', alpha=0.6)
    
    # 1차 후보군(silence_seconds)이 아니라 2차 필터링을 거친(final_silence_seconds)를 그립니다!
    for sil in final_silence_seconds:
        plt.axvspan(sil['start'], sil['end'], color='red', alpha=0.3, label='Silence')

    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys(), loc='upper right')

    plt.title('Audio Waveform with Hybrid Silence Tagging (VAD + Volume)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.tight_layout()
    plt.show()

    return final_silence_seconds

# 단독 테스트용 실행 코드
# if __name__ == "__main__":
#     detect_and_tag_silence("temp_audio.wav")