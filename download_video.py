import yt_dlp
import os

# 1. 다운로드할 유튜브 링크와 저장 경로 설정
video_url = 'https://www.youtube.com/watch?v=8uAgtotoQhM'
# 프로젝트 구조에 맞춰 backend/Data 폴더로 지정
save_path = 'backend/Data/%(title)s.%(ext)s'

# 2. 다운로드 옵션 설정 (최고 화질 + 오디오 합치기)
ydl_opts = {
    'format': 'bestvideo+bestaudio/best',
    'outtmpl': save_path,
    'noplaylist': True,
}

# 3. 다운로드 실행
try:
    print(f"📥 영상 다운로드를 시작합니다: {video_url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    print("✅ 다운로드가 완료되었습니다! backend/Data 폴더를 확인해 보세요.")
except Exception as e:
    print(f"❌ 에러가 발생했습니다: {e}")