# 파일명: viewer.py
# 기존 파형 출력 코드
import librosa
import librosa.display
import matplotlib.pyplot as plt

def display_waveform(audio_path):
    print(f"▶ 오디오 데이터 분석 및 파형 생성 중... ({audio_path})")


    y, sr = librosa.load(audio_path, sr=None)

plt.figure(figsize=(12, 4))

librosa.display.waveshow(y, sr=sr, color='blue', alpha=0.7)

plt.title('Extracted Audio Waveform')
plt.xlabel('Time (s)')
plt.ylabel('Amplitude')
plt.tight_layout()

print("파형 창을 띄웁니다.")

plt.show()