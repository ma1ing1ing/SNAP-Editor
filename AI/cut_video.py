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

kiwi = Kiwi()
os.makedirs("output", exist_ok=True)


def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds - int(seconds)) * 1000)

    return f"{hours:02}:{minutes:02}:{secs:02}.{ms:03}"


def normalize_word(word: str) -> str:
    """문장부호 제거"""
    return re.sub(r"[^\w가-힣]", "", word).strip()


def is_filler_by_kiwi(word: str) -> bool:
    """
    추임새 후보 단어인지 확인하고,
    Kiwi가 감탄사(IC)로 판단하면 추임새로 처리
    """
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
    """추임새 제거"""
    words = text.split()
    result = []

    for w in words:
        if not is_filler_by_kiwi(w):
            result.append(w)

    return " ".join(result)


def remove_repeated_words(text: str) -> str:
    """연속 반복 단어 제거"""
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
    """자막/분석용 텍스트 정제"""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    text = remove_filler_words(text)
    text = remove_repeated_words(text)

    text = re.sub(r"\s+", " ", text).strip()
    return text


def count_filler_words(text: str) -> int:
    """문장 안의 추임새 개수 계산"""
    words = text.split()
    count = 0

    for w in words:
        if is_filler_by_kiwi(w):
            count += 1

    return count


def decide_action(raw_text: str, cleaned_text: str, duration: float):
    """
    컷 편집 여부 판단
    action:
    - keep: 유지
    - remove: 삭제 추천
    """
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
 

def save_segments_to_json(segments):
    data = []

    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        duration = end - start

        raw_text = seg["text"].strip()
        cleaned = clean_text(raw_text)

        action, reason = decide_action(raw_text, cleaned, duration)

        data.append({
            "start": format_time(start),
            "end": format_time(end),
            "duration": round(duration, 3),
            "raw_text": raw_text,
            "cleaned_text": cleaned,
            "filler_count": count_filler_words(raw_text),
            "action": action,
            "reason": reason
        })

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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