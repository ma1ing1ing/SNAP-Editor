import librosa
import numpy as np
import os
import torch
import json

# API 명세서에 맞춘 함수명: detect_silence
def detect_silence(audio_path, min_silence_seconds=1.0):
    # 파일이 없으면 빈 값 리턴 (에러 방지)
    if not os.path.exists(audio_path):
        return [], {}

    model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', force_reload=False)
    (get_speech_timestamps, _, _, _, _) = utils

    y_original, sr_original = librosa.load(audio_path, sr=None)
    duration = len(y_original) / sr_original
    y_16k = librosa.resample(y_original, orig_sr=sr_original, target_sr=16000)
    audio_tensor = torch.from_numpy(y_16k)
    speech_timestamps = get_speech_timestamps(
        audio_tensor, model,
        sampling_rate=16000,
        threshold=0.3,
        min_silence_duration_ms=int(min_silence_seconds * 1000),
    )
    
    # 💡 순수 파일명 추출 (예: test_video.mp4 -> test_video)
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    
    # 💡 상세 JSON 데이터 뼈대 생성 (확장자는 .webm 하나만 깔끔하게 붙임)
    results = {
        "video_info": {"file_name": f"{base_name}.webm", "total_duration": round(duration, 2)},
        "speech_segments": [],
        "silence_segments": []
    }
    
    # 명세서 반환용 튜플 리스트 [(시작, 끝), ...]
    silence_return_list = []
    
    current_last_pos = 0.0
    s_id = 1 # 무음 구간용 ID 시작 번호
    
    for i, ts in enumerate(speech_timestamps):
        start_sec = round(ts['start'] / 16000, 2)
        end_sec = round(ts['end'] / 16000, 2)
        
        # 1. 목소리 구간 저장 (ID 포함)
        results["speech_segments"].append({
            "id": i + 1, 
            "start": start_sec, 
            "end": end_sec, 
            "duration": round(end_sec - start_sec, 2)
        })
        
        # 2. 무음 구간 계산 및 저장
        if start_sec - current_last_pos > 0.1:
            s_start = round(current_last_pos, 2)
            s_end = start_sec
            
            # JSON 딕셔너리용 상세 데이터 추가
            results["silence_segments"].append({
                "id": s_id, 
                "start": s_start, 
                "end": s_end, 
                "duration": round(s_end - s_start, 2)
            })
            # 컨트롤러 반환용 튜플 리스트 추가
            silence_return_list.append((s_start, s_end))
            s_id += 1
            
        current_last_pos = end_sec
        
    # 마지막 남은 무음 구간 처리
    if duration - current_last_pos > 0.1:
        s_start = round(current_last_pos, 2)
        s_end = round(duration, 2)
        
        results["silence_segments"].append({
            "id": s_id, 
            "start": s_start, 
            "end": s_end, 
            "duration": round(s_end - s_start, 2)
        })
        silence_return_list.append((s_start, s_end))
        
    # 🚀 기존에 있던 JSON 로컬 저장 로직은 삭제 (backend_controller.py가 대신 저장함)
    
    # 🚀 팀원 요청사항: 튜플 리스트와 상세 딕셔너리 데이터를 같이 내보냄
    return silence_return_list, results


# 파일 개별 테스트용 코드
if __name__ == "__main__":
    video_file = "Data/test_video.mp4" 
    # 반환되는 값이 두 개이므로 각각 변수로 받음
    silence_list, detailed_json_data = detect_silence(video_file)
    print("프론트로 보낼 튜플 리스트:", silence_list)
    print("\n상세 JSON 데이터 딕셔너리:", detailed_json_data)