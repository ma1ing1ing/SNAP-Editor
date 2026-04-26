import os
import re
import json
import whisper
from kiwipiepy import Kiwi

INPUT_VIDEO = "input.mp4"
OUTPUT_JSON = "output/output.json"

MODEL_SIZE = "medium"
LANGUAGE = "ko"

FILLER_WORDS = ["어", "음", "아", "그", "어어", "음음", "저", "뭐", "그러니까"]

MIN_DURATION = 0.3
SILENCE_THRESHOLD = 1.0  # 1초 이상 말이 없으면 무음구간으로 판단

kiwi = Kiwi()
os.makedirs("output", exist_ok=True)


def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


def normalize_word(word: str) -> str:
    return re.sub(r"[^\w가-힣]", "", word).strip()


def is_filler_by_kiwi(word: str) -> bool:
    clean_word = normalize_word(word)

    if clean_word not in FILLER_WORDS:
        return False

    tokens = kiwi.tokenize(clean_word)

    for token in tokens:
        if token.form == clean_word and token.tag == "IC":
            return True

    if clean_word in ["어", "음", "아", "어어", "음음"]:
        return True

    return False


def remove_filler_words(text: str) -> str:
    words = text.split()
    result = []

    for w in words:
        if not is_filler_by_kiwi(w):
            result.append(w)

    return " ".join(result)


def remove_repeated_words(text: str) -> str:
    words = text.split()

    if not words:
        return text

    cleaned_words = [words[0]]

    for w in words[1:]:
        prev = normalize_word(cleaned_words[-1])
        curr = normalize_word(w)

        if curr != prev:
            cleaned_words.append(w)

    return " ".join(cleaned_words)


def clean_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    text = remove_filler_words(text)
    text = remove_repeated_words(text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def count_filler_words(text: str) -> int:
    words = text.split()
    count = 0

    for w in words:
        if is_filler_by_kiwi(w):
            count += 1

    return count


def decide_action(raw_text: str, cleaned_text: str, duration: float):
    raw_words = raw_text.split()
    cleaned_words = cleaned_text.split()
    filler_count = count_filler_words(raw_text)

    if duration < MIN_DURATION:
        return "remove", "too_short"

    if not cleaned_text:
        return "remove", "empty_after_cleaning"

    if raw_words and filler_count / len(raw_words) >= 0.7:
        return "remove", "mostly_filler"

    if len(cleaned_words) <= 1 and filler_count >= 1:
        return "remove", "low_meaning_text"

    return "keep", "contains_meaningful_text"


def make_speech_segment(seg):
    start = float(seg["start"])
    end = float(seg["end"])
    duration = end - start

    raw_text = seg["text"].strip()
    cleaned = clean_text(raw_text)

    action, reason = decide_action(raw_text, cleaned, duration)

    return {
        "start_seconds": start,
        "end_seconds": end,
        "start": format_time(start),
        "end": format_time(end),
        "duration": round(duration, 3),
        "raw_text": raw_text,
        "cleaned_text": cleaned,
        "filler_count": count_filler_words(raw_text),
        "action": action,
        "reason": reason
    }


def make_silence_segment(start: float, end: float):
    duration = end - start

    return {
        "start_seconds": start,
        "end_seconds": end,
        "start": format_time(start),
        "end": format_time(end),
        "duration": round(duration, 3),
        "raw_text": "",
        "cleaned_text": "",
        "filler_count": 0,
        "action": "remove",
        "reason": "silence"
    }


def add_silence_segments(speech_segments):
    result = []

    for i, current in enumerate(speech_segments):
        result.append(current)

        if i < len(speech_segments) - 1:
            current_end = current["end_seconds"]
            next_start = speech_segments[i + 1]["start_seconds"]
            silence_duration = next_start - current_end

            if silence_duration >= SILENCE_THRESHOLD:
                silence_segment = make_silence_segment(current_end, next_start)
                result.append(silence_segment)

    return result


def remove_internal_seconds(data):
    cleaned_data = []

    for item in data:
        item_copy = item.copy()
        item_copy.pop("start_seconds", None)
        item_copy.pop("end_seconds", None)
        cleaned_data.append(item_copy)

    return cleaned_data


def save_segments_to_json(segments):
    speech_segments = []

    for seg in segments:
        speech_segment = make_speech_segment(seg)
        speech_segments.append(speech_segment)

    final_segments = add_silence_segments(speech_segments)

    final_segments.sort(key=lambda x: x["start_seconds"])

    output_data = remove_internal_seconds(final_segments)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{OUTPUT_JSON} 저장 완료!")


def main():
    if not os.path.exists(INPUT_VIDEO):
        print(f"오류: {INPUT_VIDEO} 파일이 없습니다.")
        return

    print("영상 확인 완료")

    try:
        print("Whisper 모델 로딩 중...")
        model = whisper.load_model(MODEL_SIZE)

        print("음성 인식 시작...")
        result = model.transcribe(
            INPUT_VIDEO,
            language=LANGUAGE,
            fp16=False
        )

    except Exception as e:
        print(f"오류 발생: {e}")
        return

    print("\n[원본 텍스트]")
    print(result["text"])

    print("\nJSON 생성 중...")
    save_segments_to_json(result["segments"])


if __name__ == "__main__":
    main()
