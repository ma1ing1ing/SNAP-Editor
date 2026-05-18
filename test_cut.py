import json, os, subprocess

def run_remove_silence_test(video_path, json_path, delete_silence_ids):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    total_duration = data["video_info"]["total_duration"]
    silence_segments = data.get("silence_segments", [])
    to_remove = [s for s in silence_segments if s['id'] in delete_silence_ids]
    to_remove.sort(key=lambda x: x['start'])
    
    keep_segments = []
    current_pos = 0.0
    for silence in to_remove:
        if silence['start'] > current_pos:
            keep_segments.append({'start': current_pos, 'end': silence['start']})
        current_pos = silence['end']
    if current_pos < total_duration:
        keep_segments.append({'start': current_pos, 'end': total_duration})
        
    base_dir = os.path.dirname(video_path)
    concat_file_path = os.path.join(base_dir, "remove_test_list.txt")
    output_video_path = os.path.join(base_dir, "deleted_silence_output.mp4")
    
    with open(concat_file_path, 'w', encoding='utf-8') as f:
        for seg in keep_segments:
            f.write(f"file '{os.path.basename(video_path)}'\n")
            f.write(f"inpoint {seg['start']}\n")
            f.write(f"outpoint {seg['end']}\n")
            
    
    command = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', 
        '-i', concat_file_path, 
        '-c:v', 'copy',  # 비디오는 원본 화질 그대로 복사 (빠름)
        '-c:a', 'aac',   # 오디오는 MP4 표준(aac)으로 변환!
        output_video_path
    ]
    
    subprocess.run(command, check=True)
    if os.path.exists(concat_file_path): os.remove(concat_file_path)
    print(f"삭제 및 인코딩 완료: {output_video_path}")

if __name__ == "__main__":
    video_file = "Data/test_video.mp4.webm"
    json_file = "Data/test_video.mp4_analysis.json"
    
    
    remove_choice = [3] 
    run_remove_silence_test(video_file, json_file, remove_choice)