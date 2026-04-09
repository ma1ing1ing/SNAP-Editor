# 파일명: editor.py
import ffmpeg
import librosa

def create_final_edited_audio(audio_path, silence_segments, output_file="./backend/Data/final_edited_audio.wav"):
    """
    무음 구간을 제외한 목소리 구간만 이어 붙임
    """
    print("\n▶ [최종 출력] 쓰레기(무음)를 버리고, 알맹이(목소리)만 이어 붙입니다...")
    
    # 1. 전체 오디오 길이 파악함
    total_duration = librosa.get_duration(path=audio_path)
    
    # 2. 살려야 할 구간 계산함
    keep_segments = []
    current_time = 0.0
    
    for sil in silence_segments:
        # 현재 시간부터 무음 시작 전까지를 말하는 구간으로 저장함
        if current_time < sil['start']:
            keep_segments.append({'start': current_time, 'end': sil['start']})
        
        # 무음이 끝나는 시간으로 이동함
        current_time = sil['end'] 
        
    # 마지막 무음 이후 끝까지의 구간 추가함
    if current_time < total_duration:
        keep_segments.append({'start': current_time, 'end': total_duration})
        
    # 3. FFmpeg로 살릴 구간만 잘라서 합침
    streams = []
    for seg in keep_segments:
        duration = seg['end'] - seg['start']
        clip = ffmpeg.input(audio_path, ss=seg['start'], t=duration)
        streams.append(clip)
        
    try:
        joined = ffmpeg.concat(*streams, v=0, a=1)
        joined = ffmpeg.output(joined, output_file)
        ffmpeg.run(joined, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        print(f"✅ 최종 편집 파일 생성 완료: {output_file}")
        
    except ffmpeg.Error as e:
        print("❌ FFmpeg 클립 생성 중 에러 발생")
        if e.stderr:
            print(e.stderr.decode('utf-8'))

def create_final_edited_video(video_path, silence_segments, output_file="./backend/Data/final_edited_video.mp4"):
    """
    무음 구간을 제외한 '영상(비디오+오디오)' 구간을 잘라서 이어 붙임
    """
    print("\n▶ [최종 출력] 비디오 렌더링 중... (영상이라 시간이 조금 걸릴 수 있습니다!)")
    
    # 1. 영상 원본의 전체 길이(초)를 파악함
    try:
        probe = ffmpeg.probe(video_path)
        total_duration = float(probe['format']['duration'])
    except Exception as e:
        print("❌ 영상 길이 파악 실패. 원본 영상 경로를 확인해 주세요.")
        return

    # 2. 살려야 할 구간(목소리 구간) 계산함
    keep_segments = []
    current_time = 0.0
    
    for sil in silence_segments:
        if current_time < sil['start']:
            keep_segments.append({'start': current_time, 'end': sil['start']})
        current_time = sil['end'] 
        
    if current_time < total_duration:
        keep_segments.append({'start': current_time, 'end': total_duration})
        
    # 3. FFmpeg로 비디오와 오디오를 동시에 자르고 병합(Concat)함
    streams = []
    for seg in keep_segments:
        duration = seg['end'] - seg['start']
        # 영상을 해당 시간만큼 자름
        clip = ffmpeg.input(video_path, ss=seg['start'], t=duration)
        # 비디오(화면)와 오디오(소리) 스트림을 각각 리스트에 담음
        streams.append(clip.video)
        streams.append(clip.audio)
        
    try:
        # v=1(비디오), a=1(오디오)를 쌍으로 묶어서 순서대로 이어 붙임
        joined = ffmpeg.concat(*streams, v=1, a=1)
        joined = ffmpeg.output(joined, output_file)
        
        # 실제 렌더링 실행
        ffmpeg.run(joined, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        print(f"✅ 최종 편집 영상(MP4) 생성 완료: {output_file}")
        print("🎬 이 영상을 재생해 보세요! 숨소리 구간에서 화면이 '팟' 하고 넘어가는 점프 컷을 볼 수 있습니다.")
        
    except ffmpeg.Error as e:
        print("❌ FFmpeg 비디오 렌더링 중 에러 발생")
        if e.stderr:
            print(e.stderr.decode('utf-8'))