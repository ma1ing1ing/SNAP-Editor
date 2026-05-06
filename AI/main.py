<<<<<<< HEAD
<<<<<<< Updated upstream
# =============================================================
# SNAP Editor — AI 필터(NLP) 메인 파이프라인 (Python 3.10)
# 설계 문서: ./AI 필터(NLP) 구축 구상도.md
#
# [구상도 단계 → 함수]
#   1단계 타겟 품사 정의 : stopwords_ko.json + load_stopwords
#   2단계 1차 사전 매칭   : pass_first_filter
#   2단계 2차 품사 검증   : pass_second_filter (Kiwi)
#   3단계 크로스 체크     : is_filler
#   4단계 듀얼 출력       : split_words_by_filter
#                          + build_subtitle_segment
#                          + build_cut_entries
#                          + save_dual_outputs
#
# [v1 → v2 변경 요약]
#   · 처리 단위 : 문장(str)  →  단어(dict, start/end 포함)
#                Whisper 호출에 word_timestamps=True 추가
#   · 검문 규칙 : 그대로 (is_filler 재사용)
#   · 출력      : output.json 한 개  →
#                 output/subtitles.json (자막용) +
#                 output/cut.json      (컷편집용)
#
# [입력/출력]
#   입력 : input.mp4
#   출력 : output/subtitles.json, output/cut.json
# =============================================================
=======
>>>>>>> 5de2cc054b7cfc8fb8bf519589302ac83527825e
import os
import re
import json
import whisper
from pathlib import Path
from kiwipiepy import Kiwi


INPUT_VIDEO = "input.mp4"

OUTPUT_DIR = "output"
CUT_JSON = "output/cut.json"
SUBTITLE_JSON = "output/subtitles.json"
SRT_PATH = "output/subtitles.srt"

MODEL_SIZE = "medium"
LANGUAGE = "ko"

MIN_DURATION = 0.3
SILENCE_THRESHOLD = 1.0

STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"
STOPWORD_MODE = "default"

kiwi = Kiwi()
os.makedirs(OUTPUT_DIR, exist_ok=True)


# 불용어 설정 불러오기
def load_stopwords(mode: str = "default"):
    if not STOPWORDS_PATH.exists():
        raise FileNotFoundError(f"{STOPWORDS_PATH} 파일이 없습니다.")

    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data["modes"].get(mode, data["modes"]["default"])
    return cfg["words"], cfg["target_pos"]


FILLER_WORDS, TARGET_POS = load_stopwords(STOPWORD_MODE)


# JSON용 시간 형식
def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


# SRT용 시간 형식
def format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{secs:02},{ms:03}"


# 단어 정규화
def normalize_word(word: str) -> str:
    return re.sub(r"[^\w가-힣]", "", word).strip()
=======
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
        # 3. 각 구간을 개별 mp4 조각으로 인코딩
        for i, seg in enumerate(keep_segments):
            duration = seg['end'] - seg['start']
            temp_clip = os.path.join(TEMP_DIR, f"clip_{i}.mp4")
            
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

        # 5. 모든 조각을 하나로 병합 (스트림 복사)
        merge_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', list_file_path,
            '-c', 'copy',            # 이미 조각들이 완벽한 CFR이므로 단순 복사 수행
            output_file
        ]
        subprocess.run(merge_cmd, check=True)
        print(f"✅ 최종 편집 영상 생성 완료: {output_file}")

    except Exception as e:
        print(f"❌ 렌더링 중 치명적 오류 발생: {e}")

    finally:
        # 6. 임시 파일 정리
        print("🧹 임시 파일 정리 중...")
        for cf in clip_files:
            if os.path.exists(cf): os.remove(cf)
        if os.path.exists(list_file_path): os.remove(list_file_path)
>>>>>>> Stashed changes


<<<<<<< HEAD
<<<<<<< Updated upstream
def pass_second_filter(word: str) -> bool:
    # 2차: Kiwi 품사 결과가 TARGET_POS(타깃 품사)에 속하는지 확인
    clean = normalize_word(word)
    tockens = kiwi.tokenize(clean)
    for t in tockens:
        if t.form == clean and t.tag in TARGET_POS:
            return True
    return False
#True -> 불용어로 삭제 대상, False -> 정상 단어로 유지
def is_filler(word: str) -> bool:
    #1차 통과 -> 2차 검문
    if not pass_first_filter(word):
=======
# 불용어 여부 판별
def classify_filler(word: str) -> bool:
    clean_word = normalize_word(word)

    if clean_word not in FILLER_WORDS:
>>>>>>> 5de2cc054b7cfc8fb8bf519589302ac83527825e
        return False

    tokens = kiwi.tokenize(clean_word)

    for token in tokens:
        if token.form == clean_word and token.tag in TARGET_POS:
            return True

    return False


# 유지 단어 / 제거 단어 분리
def filter_text(words):
    kept_words = []
    cut_words = []
    prev_word = None

    for w in words:
        word = w["word"].strip()

        if not word:
            continue

        token = {
            "word": word,
            "start": float(w["start"]),
            "end": float(w["end"])
        }

        if classify_filler(word):
            token["reason"] = "filler"
            cut_words.append(token)
            continue

        current_word = normalize_word(word)

        if current_word and current_word == prev_word:
            token["reason"] = "repeated"
            cut_words.append(token)
            continue

        kept_words.append(token)
        prev_word = current_word

    return kept_words, cut_words


# Whisper 음성 인식
def transcribe(video_path: str):
    model = whisper.load_model(MODEL_SIZE)

    result = model.transcribe(
        video_path,
        language=LANGUAGE,
        fp16=False,
        word_timestamps=True
    )

    return result["segments"]


# 무음 구간 탐지
def detect_silence(segments):
    silence_list = []

    for i in range(len(segments) - 1):
        current_end = float(segments[i]["end"])
        next_start = float(segments[i + 1]["start"])

        silence_duration = next_start - current_end

        if silence_duration >= SILENCE_THRESHOLD:
            silence_list.append({
                "start": current_end,
                "end": next_start,
                "duration": round(silence_duration, 3),
                "reason": "silence"
            })

    return silence_list


# 컷 여부 판단
def decide_cut(original_text: str, cleaned_text: str, segment_time: tuple):
    start, end = segment_time
    duration = end - start

    if duration < MIN_DURATION:
        return "remove"

    if not cleaned_text.strip():
        return "remove"

    return "keep"


# 인접한 제거 단어 병합
def merge_cut_words(cut_words):
    merged = []

    for w in cut_words:
        if merged and w["start"] - merged[-1]["end_seconds"] <= 0.05:
            merged[-1]["end_seconds"] = w["end"]
            merged[-1]["words"].append(w["word"])
            merged[-1]["reasons"].append(w.get("reason", "filler"))
        else:
            merged.append({
                "start_seconds": w["start"],
                "end_seconds": w["end"],
                "words": [w["word"]],
                "reasons": [w.get("reason", "filler")]
            })

    return merged


# 편집점 생성
def generate_cut_points(segments, silence_list):
    subtitles = []
    cut_points = []

    for seg in segments:
        words = seg.get("words", [])

        if not words:
            continue

        kept_words, cut_words = filter_text(words)

        if kept_words:
            cleaned_text = " ".join(w["word"] for w in kept_words)

            action = decide_cut(
                original_text=seg.get("text", ""),
                cleaned_text=cleaned_text,
                segment_time=(kept_words[0]["start"], kept_words[-1]["end"])
            )

            if action == "keep":
                subtitles.append({
                    "start": format_time(kept_words[0]["start"]),
                    "end": format_time(kept_words[-1]["end"]),
                    "start_seconds": kept_words[0]["start"],
                    "end_seconds": kept_words[-1]["end"],
                    "text": cleaned_text
                })

        merged_cut_words = merge_cut_words(cut_words)

        for item in merged_cut_words:
            cut_points.append({
                "start": format_time(item["start_seconds"]),
                "end": format_time(item["end_seconds"]),
                "start_seconds": item["start_seconds"],
                "end_seconds": item["end_seconds"],
                "duration": round(item["end_seconds"] - item["start_seconds"], 3),
                "removed_text": " ".join(item["words"]),
                "reason": ", ".join(sorted(set(item["reasons"])))
            })

    for silence in silence_list:
        cut_points.append({
            "start": format_time(silence["start"]),
            "end": format_time(silence["end"]),
            "start_seconds": silence["start"],
            "end_seconds": silence["end"],
            "duration": silence["duration"],
            "removed_text": "",
            "reason": "silence"
        })

    cut_points.sort(key=lambda x: x["start_seconds"])
    return subtitles, cut_points


# SRT 생성
def generate_srt(subtitles, output_path: str):
    with open(output_path, "w", encoding="utf-8") as f:
        for idx, sub in enumerate(subtitles, start=1):
            start = format_srt_time(sub["start_seconds"])
            end = format_srt_time(sub["end_seconds"])

            f.write(f"{idx}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{sub['text']}\n\n")

    return output_path


# JSON 저장
def save_json(data, output_path: str):
    cleaned_data = []

    for item in data:
        item_copy = item.copy()
        item_copy.pop("start_seconds", None)
        item_copy.pop("end_seconds", None)
        cleaned_data.append(item_copy)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)


# 실행
def main():
    if not os.path.exists(INPUT_VIDEO):
        print(f"오류: {INPUT_VIDEO} 파일이 없습니다.")
        return

    print("영상 확인 완료")
    print(f"불용어 모드: {STOPWORD_MODE}")
    print("Whisper 음성 인식 시작...")

    try:
        segments = transcribe(INPUT_VIDEO)
    except Exception as e:
        print(f"Whisper 처리 중 오류 발생: {e}")
        return

    print("무음 구간 탐지 중...")
    silence_list = detect_silence(segments)

    print("편집점 생성 중...")
    subtitles, cut_points = generate_cut_points(segments, silence_list)

    save_json(cut_points, CUT_JSON)
    save_json(subtitles, SUBTITLE_JSON)
    generate_srt(subtitles, SRT_PATH)

    print("\nAI 처리 완료!")
    print(f"편집점 JSON 저장: {CUT_JSON}")
    print(f"확인용 자막 JSON 저장: {SUBTITLE_JSON}")
    print(f"확인용 SRT 저장: {SRT_PATH}")


if __name__ == "__main__":
    main()
=======
def add_subtitles_to_video(video_input, srt_input, video_output, language='ko'):
    """
    편집된 영상에 자막(SRT)을 메타데이터 트랙으로 심어줍니다. (소프트인코딩 방식)
    재인코딩 없이 스트림을 복사하므로 속도가 매우 빠릅니다.
    """
    print(f"\n▶ [인코딩] 자막 트랙 추가 시작... (언어: {language})")
    
    # FFmpeg 언어 코드 매핑
    lang_map = {'ko': 'kor', 'en': 'eng', 'ja': 'jpn', 'zh': 'chi'}
    ffmpeg_lang = lang_map.get(language, language)

    # 🌟 소프트인코딩 핵심 명령어 (mov_text 코덱 고정)
    command = [
        'ffmpeg', '-y',
        '-i', video_input,       
        '-i', srt_input,         
        '-c:v', 'copy',          
        '-c:a', 'copy',          
        '-c:s', 'mov_text',      
        f'-metadata:s:s:0', f'language={ffmpeg_lang}', 
        '-disposition:s:0', 'default', 
        video_output
    ]
    
    try:
        subprocess.run(command, check=True)
        print(f"✅ 소프트인코딩 자막 추가 성공: {video_output}")
    except subprocess.CalledProcessError as e:
        print(f"❌ 자막 추가 실패 (FFmpeg 오류): {e}")
>>>>>>> Stashed changes
