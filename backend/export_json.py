import librosa, numpy as np, os, torch, json

def run_vad_and_export_json(audio_path):
    if not os.path.exists(audio_path): return
    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
    (get_speech_timestamps, _, _, _, _) = utils
    
    y_original, sr_original = librosa.load(audio_path, sr=None)
    duration = len(y_original) / sr_original
    y_16k = librosa.resample(y_original, orig_sr=sr_original, target_sr=16000)
    audio_tensor = torch.from_numpy(y_16k)
    speech_timestamps = get_speech_timestamps(audio_tensor, model, sampling_rate=16000)
    
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_filename = f"{base_name}_analysis.json"
    
    results = {
        "video_info": {"file_name": os.path.basename(audio_path), "total_duration": round(duration, 2)},
        "speech_segments": [],
        "silence_segments": []
    }
    
    current_last_pos = 0.0
    s_id = 1 # 무음 구간용 ID 시작 번호
    
    for i, ts in enumerate(speech_timestamps):
        start_sec = round(ts['start'] / 16000, 2)
        end_sec = round(ts['end'] / 16000, 2)
        
        # 목소리 구간 저장 (ID 포함)
        results["speech_segments"].append({"id": i + 1, "start": start_sec, "end": end_sec, "duration": round(end_sec - start_sec, 2)})
        
        # 무음 구간 계산 및 저장 (ID 추가!)
        if start_sec - current_last_pos > 0.1:
            results["silence_segments"].append({
                "id": s_id, 
                "start": round(current_last_pos, 2), 
                "end": start_sec, 
                "duration": round(start_sec - current_last_pos, 2)
            })
            s_id += 1
        current_last_pos = end_sec
        
    if duration - current_last_pos > 0.1:
        results["silence_segments"].append({"id": s_id, "start": round(current_last_pos, 2), "end": round(duration, 2), "duration": round(duration - current_last_pos, 2)})
        
    output_path = os.path.join(os.path.dirname(audio_path), output_filename)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=4, ensure_ascii=False)
    print(f"새로운 JSON 생성 완료: {output_path}")

if __name__ == "__main__":
    video_file = "Data/test_video.mp4.webm"
    run_vad_and_export_json(video_file)