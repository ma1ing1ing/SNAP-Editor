# 파일명: viewer.py
import librosa
import librosa.display
import matplotlib.pyplot as plt
import os
import numpy as np

def display_waveform_with_silence(audio_path, silence_segments=None):
    """
    오디오 파일의 파형을 시각화하고, 무음 구간을 빨간색으로 하이라이트합니다.
    화면에 대화형 창을 띄워 마우스로 파형을 확대/축소하며 직접 확인할 수 있습니다.
    """
    print(f"\n▶ [시각화] 파형 및 무음 구간 표시 창 로드 중... ({audio_path})")
    
    if not os.path.exists(audio_path):
        print("❌ 에러: 분석할 오디오 파일이 없습니다.")
        return

    # 오디오 로드 (1시간 이상 영상은 로드에 몇 초 정도 걸릴 수 있습니다)
    y, sr = librosa.load(audio_path, sr=None)

    plt.figure(figsize=(14, 5))
    
    # 1. 파형 그리기 (파란색)
    librosa.display.waveshow(y, sr=sr, color='blue', alpha=0.6)
    
    # 2. 무음 구간 태깅 (빨간색 영역)
    if silence_segments:
        for sil in silence_segments:
            plt.axvspan(sil['start'], sil['end'], color='red', alpha=0.3, label='Silence')
            
        # 중복된 범례(Legend) 하나로 합치기
        handles, labels = plt.gca().get_legend_handles_labels()
        if handles:
            by_label = dict(zip(labels, handles))
            plt.legend(by_label.values(), by_label.keys(), loc='upper right')
            
    plt.title('Audio Waveform with Silence Tagging (Interactive View)')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.tight_layout()

    print("파형 창을 띄웁니다.")
    print("⚠️ 주의: 띄워진 창을 [X] 버튼으로 닫아야 다음 파이프라인이 이어서 진행됩니다.")
    
    # 화면에 창 띄우기 (이 코드가 실행되면 창을 닫을 때까지 대기합니다)
    plt.show()

def get_waveform_data(audio_path, num_points=100000):
    """
    프론트엔드 시각화용 파형 데이터를 추출하여 반환합니다.
    num_points: 프론트엔드로 넘길 점의 개수 (너무 많으면 UI가 버벅임)
    """
    if not os.path.exists(audio_path):
        print("❌ 에러: 분석할 오디오 파일이 없습니다.")
        return None, None, None

    y, sr = librosa.load(audio_path, sr=None)
    
    # 1. 프론트엔드가 그리기 쉽도록 데이터 개수 축소 (Downsampling)
    # 예: 100만개의 샘플을 num_points개로 압축 (최대/최소값 위주로)
    samples_per_point = len(y) // num_points
    if samples_per_point > 0:
        # 모양을 2D로 만들어서 각 구간별 최대/최소, 혹은 평균 진폭을 구함
        y_reshaped = y[:samples_per_point * num_points].reshape(num_points, samples_per_point)
        # 시각화에는 윤곽선이 중요하므로 최대 진폭을 주로 사용
        y_downsampled = np.max(np.abs(y_reshaped), axis=1) 
    else:
        y_downsampled = y
        
    # 총 길이(초) 계산
    duration = librosa.get_duration(y=y, sr=sr)
    
    # 2. 오디오 파형 배열, 샘플레이트, 총 길이 리턴
    return y_downsampled.tolist(), sr, float(duration)
