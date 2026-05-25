import librosa
import librosa.display
import matplotlib.pyplot as plt
import numpy as np
import os
import torch

def run_advanced_vad_and_silence(audio_path, target_points=2000):
    if not os.path.exists(audio_path):
        return

    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
    (get_speech_timestamps, _, _, _, _) = utils

    y_original, sr_original = librosa.load(audio_path, sr=None)
    duration = len(y_original) / sr_original
    
    y_16k = librosa.resample(y_original, orig_sr=sr_original, target_sr=16000)
    audio_tensor = torch.from_numpy(y_16k)
    speech_timestamps = get_speech_timestamps(audio_tensor, model, sampling_rate=16000)

    hop_length = len(y_original) // target_points
    resampled_max = []
    resampled_min = []
    for i in range(0, len(y_original), hop_length):
        chunk = y_original[i:i+hop_length]
        if len(chunk) > 0:
            resampled_max.append(np.max(chunk))
            resampled_min.append(np.min(chunk))

    print(f"\n===== SNAP-EDITOR 백엔드 데이터 분석 리포트 =====")
    print(f"영상 총 길이: {duration:.2f}초")
    
    current_last_pos = 0.0
    silence_count = 1

    plt.figure(figsize=(15, 5))
    x_axis = np.linspace(0, duration, len(resampled_max))
    plt.fill_between(x_axis, resampled_min, resampled_max, color='blue', alpha=0.2)

    for ts in speech_timestamps:
        start_sec = ts['start'] / 16000
        end_sec = ts['end'] / 16000
        
        if start_sec - current_last_pos > 0.1:
            print(f"[무음 {silence_count}] {current_last_pos:.2f}초 ~ {start_sec:.2f}초 (약 {start_sec - current_last_pos:.2f}초)")
            silence_count += 1
            
        plt.axvspan(start_sec, end_sec, color='red', alpha=0.4)
        current_last_pos = end_sec

    if duration - current_last_pos > 0.1:
        print(f"[무음 {silence_count}] {current_last_pos:.2f}초 ~ {duration:.2f}초 (약 {duration - current_last_pos:.2f}초)")

    plt.title('SNAP-Editor V1: AI Voice Detection & Silence Logic')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude')
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    video_file = "Data/test_video.mp4.webm" 
    run_advanced_vad_and_silence(video_file)