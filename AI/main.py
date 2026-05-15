import os
import re
import json
import whisper
from pathlib import Path
from collections import Counter
from kiwipiepy import Kiwi


INPUT_VIDEO = "input.mp4"

OUTPUT_DIR = "output"
CUT_JSON = "output/cut.json"
SUBTITLE_JSON = "output/subtitles.json"
SRT_PATH = "output/subtitles.srt"

MODEL_SIZE = "medium"
LANGUAGE = "ko"

MIN_DURATION = 0.3

STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"
STOPWORD_MODE = "default"

# 말버릇 후보 단어
HABIT_WORDS = [
    "진짜", "약간", "그냥", "뭔가", "이제",
    "사실", "막", "아니", "뭐랄까", "그래서"
]

# 몇 번 이상 나오면 말버릇으로 판단할지
HABIT_MIN_COUNT = 3

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


# 불용어 여부 판별
def classify_filler(word: str) -> bool:
    clean_word = normalize_word(word)

    if clean_word not in FILLER_WORDS:
        return False

    tokens = kiwi.tokenize(clean_word)

    for token in tokens:
        if token.form == clean_word and token.tag in TARGET_POS:
            return True

    return False


# 영상 전체에서 말버릇 단어 빈도 분석
def get_habit_words(segments):
    word_count = Counter()

    for seg in segments:
        words = seg.get("words", [])

        for w in words:
            word = normalize_word(w["word"].strip())

            if word in HABIT_WORDS:
                word_count[word] += 1

    detected_habits = {
        word for word, count in word_count.items()
        if count >= HABIT_MIN_COUNT
    }

    print("\n말버릇 단어 빈도:")
    for word, count in word_count.items():
        print(f"{word}: {count}회")

    print(f"\n말버릇으로 판단된 단어: {list(detected_habits)}")

    return detected_habits


# 유지 단어 / 제거 단어 분리
def filter_text(words, detected_habits):
    kept_words = []
    cut_words = []
    prev_word = None

    for w in words:
        word = w["word"].strip()

        if not word:
            continue

        clean_word = normalize_word(word)

        token = {
            "word": word,
            "start": float(w["start"]),
            "end": float(w["end"])
        }

        if classify_filler(word):
            token["reason"] = "filler"
            cut_words.append(token)
            continue

        if clean_word in detected_habits:
            token["reason"] = "habit"
            cut_words.append(token)
            continue

        if clean_word and clean_word == prev_word:
            token["reason"] = "repeated"
            cut_words.append(token)
            continue

        kept_words.append(token)
        prev_word = clean_word

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
def generate_cut_points(segments, detected_habits):
    subtitles = []
    cut_points = []

    for seg in segments:
        words = seg.get("words", [])

        if not words:
            continue

        kept_words, cut_words = filter_text(words, detected_habits)

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

    print("말버릇 빈도 분석 중...")
    detected_habits = get_habit_words(segments)

    print("불용어 및 말버릇 기반 편집점 생성 중...")
    subtitles, cut_points = generate_cut_points(segments, detected_habits)

    save_json(cut_points, CUT_JSON)
    save_json(subtitles, SUBTITLE_JSON)
    generate_srt(subtitles, SRT_PATH)

    print("\nAI 처리 완료!")
    print(f"편집점 JSON 저장: {CUT_JSON}")
    print(f"확인용 자막 JSON 저장: {SUBTITLE_JSON}")
    print(f"확인용 SRT 저장: {SRT_PATH}")


if __name__ == "__main__":
    main()
