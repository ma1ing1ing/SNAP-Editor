import subprocess
import os
import ffmpeg

# 임시 클립들이 저장될 폴더 (자동 생성)
TEMP_DIR = "./backend/Data/temp_clips"
os.makedirs(TEMP_DIR, exist_ok=True)

def create_final_edited_video(video_path, silence_segments, output_file="./backend/Data/final_edited_video.mp4"):
    """
    무음 구간을 제외한 영상을 '개별 조각 렌더링 -> 리스트 병합' 방식으로 처리합니다.
    CFR(고정 프레임) 강제 적용으로 싱크 밀림 현상을 원천 차단합니다.
    """
    print("\n▶ 비디오 렌더링 및 싱크 안정화 작업 시작...")

    # 1. 영상 전체 길이 파악
    try:
        probe = ffmpeg.probe(video_path)
        total_duration = float(probe['format']['duration'])
    except Exception as e:
        print(f"❌ 영상 길이 파악 실패. 원본 경로를 확인해 주세요: {e}")
        return

    # 2. 목소리 구간(살릴 구간) 계산
    keep_segments = []
    current_time = 0.0
    for sil in silence_segments:
        if current_time < sil['start']:
            keep_segments.append({'start': current_time, 'end': sil['start']})
        current_time = sil['end']
    if current_time < total_duration:
        keep_segments.append({'start': current_time, 'end': total_duration})

    total_keep_time = sum([s['end'] - s['start'] for s in keep_segments])
    print(f"📊 분석 결과: 총 {len(keep_segments)}개의 목소리 구간 발견")
    print(f"📊 예상 편집본 길이: {total_keep_time / 60:.2f}분")

    clip_files = []
    list_file_path = os.path.join(TEMP_DIR, "inputs.txt")

    try:
        # 3. 각 구간을 개별 조각으로 인코딩 (.ts 포맷 사용 시 병합 과정의 오디오 딜레이/싱크 밀림을 방지합니다)
        for i, seg in enumerate(keep_segments):
            duration = seg['end'] - seg['start']
            temp_clip = os.path.join(TEMP_DIR, f"clip_{i}.ts")
            
            # [핵심] 조각 생성 시 싱크 정렬 옵션 강화
            cmd = [
                'ffmpeg', '-y',
                '-ss', str(seg['start']),
                '-t', str(duration),
                '-i', video_path,
                '-c:v', 'libx264', '-preset', 'ultrafast',
                '-r', '30',              # 프레임 레이트 고정
                '-vsync', 'cfr',         # 가변 프레임 -> 고정 프레임 강제 변환
                '-c:a', 'aac',
                '-ar', '44100',          # 오디오 샘플링 레이트 통일
                '-async', '1',           # 오디오 시작점 강제 보정
                '-avoid_negative_ts', 'make_zero',
                '-map_metadata', '-1',
                temp_clip
            ]
            
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            clip_files.append(temp_clip)
            
            if (i + 1) % 50 == 0:
                print(f" 진행 중... ({i + 1}/{len(keep_segments)} 조각 완료)")

        # 4. FFmpeg concat용 리스트 파일 작성
        with open(list_file_path, "w", encoding="utf-8") as f:
            for clip in clip_files:
                f.write(f"file '{os.path.abspath(clip)}'\n")

        # 5. 모든 조각을 하나로 병합
        # 비디오는 복사(copy)하되, 오디오는 aac로 재인코딩하여 
        # 수백 개의 조각 병합 시 발생하는 오디오 타임스탬프(DTS) 꼬임 및 
        # 자막 싱크 밀림(프레임 드롭) 현상을 원천 차단합니다.
        merge_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file_path,
            '-c:v', 'copy',          # 비디오는 화질 저하 없이 복사
            '-c:a', 'aac',           # 오디오는 재인코딩하여 타임스탬프 완벽 재정렬
            '-b:a', '192k',          # 오디오 비트레이트 (음질 보존)
            '-af', 'aresample=async=1', # 미세한 오디오 싱크 어긋남 강제 보정
            output_file
        ]
        subprocess.run(merge_cmd, check=True)
        print(f"✅ 최종 편집 영상 생성 완료: {output_file}")
        return output_file

    except Exception as e:
        print(f"❌ 렌더링 중 치명적 오류 발생: {e}")
        return None

    finally:
        # 6. 임시 파일 정리
        print("🧹 임시 파일 정리 중...")
        for cf in clip_files:
            if os.path.exists(cf): os.remove(cf)
        if os.path.exists(list_file_path): os.remove(list_file_path)


def add_subtitles_to_video(video_input, srt_input, video_output, language='ko'):
    """
    편집된 영상에 자막(SRT)을 메타데이터 트랙으로 심어줍니다. (소프트인코딩 방식)
    재인코딩 없이 스트림을 복사하므로 속도가 매우 빠릅니다.
    """
    print(f"\n▶ [인코딩] 자막 트랙 추가 시작... (언어: {language})")
    
    # FFmpeg 언어 코드 매핑
    lang_map = {'ko': 'kor', 'en': 'eng', 'ja': 'jpn', 'zh': 'chi'}
    ffmpeg_lang = lang_map.get(language, language)

    # 🌟 소프트인코딩 핵심 명령어
    command = [
        'ffmpeg', '-y',
        '-i', video_input,       # 입력 영상
        '-i', srt_input,         # 입력 자막
        '-c:v', 'copy',          # 비디오 재인코딩 안 함 (복사)
        '-c:a', 'copy',          # 오디오 재인코딩 안 함 (복사)
        '-c:s', 'mov_text',      # mp4 표준 자막 코덱인 mov_text 사용
        f'-metadata:s:s:0', f'language={ffmpeg_lang}', # 자막 언어 메타데이터 설정
        '-disposition:s:0', 'default', # 기본 자막으로 활성화
        video_output
    ]
    
    try:
        # 💡 shell=False로 설정하여 경로 문제 최소화
        subprocess.run(command, check=True)
        print(f"✅ 소프트인코딩 자막 추가 성공: {video_output}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ 자막 추가 실패: {e}")
        # 만약 mov_text에서 에러가 나면 좀 더 범용적인 srt 코덱으로 재시도
        print("🔄 코덱 변경 후 재시도 중...")
        try:
            command[10] = 'srt' 
            subprocess.run(command, check=True)
            return True
        except:
            return False