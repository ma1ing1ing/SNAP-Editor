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
import os
import re
import json
import whisper
from pathlib import Path
from kiwipiepy import Kiwi

# 입력/출력 경로 설정
INPUT_VIDEO = "input.mp4"
#OUTPUT_JSON = "output/output.json" # 미사용

# Whisper 모델 옵션
MODEL_SIZE = "medium"
LANGUAGE = "ko"

STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"

# 불용어 후보 단어 목록(1차 필터) : 23 ~ 30
# FILLER_WORDS = ["어", "음", "아", "그", "어어", "음음", "저", "뭐", "그러니까"] 를 동적으로 교체
# stopwords_ko.json 파일만 수정하면 코드 변경 없이 불용어를 추가/삭제 가능 
def load_stopwords(mode: str = "default") -> list[str]:
    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    cfg = data["modes"].get(mode, {"words": [], "target_pos": ["IC"]})
    return cfg["words"], cfg["target_pos"]

STOPWORD_MODE = "default" # 어던 강도/불용어를 사용할지 골라두는 설정값
FILLER_WORDS, TARGET_POS = load_stopwords(STOPWORD_MODE) 

# 컷 편집 기준 임계값
MIN_DURATION = 0.3
SILENCE_THRESHOLD = 1.0  # 1초 이상 말이 없으면 무음구간으로 판단

# 형태소 분석기 초기화 및 출력 폴더 생성
kiwi = Kiwi()
os.makedirs("output", exist_ok=True)

def format_time(seconds: float) -> str:
    # 초 단위를 HH:MM:SS 문자열로 변환
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


def normalize_word(word: str) -> str:
    # 비교를 위해 문장부호를 제거하고 공백을 정리
    return re.sub(r"[^\w가-힣]", "", word).strip()

# 54 ~ 71 : 불용어 필터
def pass_first_filter(word: str) -> bool:
    # 1차: FILLER_WORDS에 있는지 확인
    return normalize_word(word) in FILLER_WORDS

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
        return False
    return pass_second_filter(word)

# 미사용
def remove_filler_words(text: str) -> str:
    # 문장 내 추임새만 제거
    words = text.split()
    result = []

    for w in words:
        if not is_filler(w):
            result.append(w)

    return " ".join(result)

# 미사용
def remove_repeated_words(text: str) -> str:
    # 연속해서 반복되는 동일 단어를 하나로 정리
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

# 미사용
def clean_text(text: str) -> str:
    # 자막용 텍스트 정제: 공백 정리 -> 추임새 제거 -> 반복 단어 제거
    text = text.strip()
    text = re.sub(r"\s+", " ", text)

    text = remove_filler_words(text)
    text = remove_repeated_words(text)

    text = re.sub(r"\s+", " ", text).strip()
    return text

# 미사용
def count_filler_words(text: str) -> int:
    # 원문 기준 추임새 개수 집계
    words = text.split()
    count = 0

    for w in words:
        if is_filler(w):
            count += 1

    return count

# 미사용
def decide_action(raw_text: str, cleaned_text: str, duration: float):
    # 세그먼트를 유지/삭제할지 규칙 기반으로 판단
    raw_words = raw_text.split()
    cleaned_words = cleaned_text.split()
    filler_count = count_filler_words(raw_text)

    # 길이가 너무 짧은 구간은 제거
    if duration < MIN_DURATION:
        return "remove", "too_short"

    # 정제 후 텍스트가 비면 제거
    if not cleaned_text:
        return "remove", "empty_after_cleaning"

    # 원문에서 추임새 비율이 높으면 제거
    if raw_words and filler_count / len(raw_words) >= 0.7:
        return "remove", "mostly_filler"

    # 의미 단어가 거의 없고 추임새만 남는 경우 제거
    if len(cleaned_words) <= 1 and filler_count >= 1:
        return "remove", "low_meaning_text"

    return "keep", "contains_meaningful_text"

#기존 : clean_text(text)가 문자열 -> 문자열로만 동작해 시간 정보 사라짐.
#현재 : 단어 객체(시간 포함)리스트를 입력/출력으로 받게 바꿈. 
#핵심 : 버려진 단어를 그냥 버리지 않고 cut_words에 시간과 함께 담고, 출력 2의 원료가 된다.
def split_words_by_filter(seg):
    """
    Whisper segment의 words를 두 갈래로 분리:
    - kept_words : 자막에 남을 단어 (시간 포함)
    - cut_words  : 컷편집 대상 단어 (시간만 필요)
    """
    kept_words, cut_words = [], []
    prev_kept_norm = None

    for w in seg.get("words", []):
        token = {
            "word": w["word"].strip(),
            "start": float(w["start"]),
            "end": float(w["end"]),
        }
        if not token["word"]:
            continue
        
        if is_filler(token["word"]):
            cut_words.append(token)
            continue

        #연속 반복 단어 제거도 단어 단위로
        curr_norm = normalize_word(token["word"])
        if curr_norm and curr_norm == prev_kept_norm:
            cut_words.append({**token, "reason": "repeated"})
            continue

        kept_words.append(token)
        prev_kept_norm = curr_norm
    return kept_words, cut_words

# 미사용
def make_silence_segment(start: float, end: float):
    # 발화 사이 무음 구간을 제거 후보 세그먼트로 생성
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

# 미사용
def add_silence_segments(speech_segments):
    # 인접 발화 사이 간격이 임계값 이상이면 무음 세그먼트를 추가
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

# 미사용
def remove_internal_seconds(data):
    # 내부 계산용 필드를 제거해 최종 출력 포맷으로 정리
    cleaned_data = []

    for item in data:
        item_copy = item.copy()
        item_copy.pop("start_seconds", None)
        item_copy.pop("end_seconds", None)
        cleaned_data.append(item_copy)

    return cleaned_data

#기존: 하나의 JSON
#현재: 두갈래 JSON
SUBTITLE_JSON = "output/subtitles.json" #출력 1 (텍스트 에디터용)
CUTS_JSON = "output/cut.json" #출력 2 (컷편집용)

#참고: seg 매개변수는 지금 본문에선 안 쓰지만, 나중에 “원래 segment 의 raw text도 같이 저장” 같은 확장을 위해 받아두는 형태로 지금 안쓰면 빼도 됨.
def build_subtitle_segment(seg, kept_words):
    if not kept_words:
        return None
    return {
        "start": format_time(kept_words[0]["start"]),
        "end": format_time(kept_words[-1]["end"]),
        "text": " ".join(w["word"] for w in kept_words),
    }

def build_cut_entries(cut_words):
    #인접한 cut 단어는 하나의 컷 구간으로 병합
    merged = []
    for w in cut_words:
        if merged and w["start"] - merged[-1]["end"] <= 0.05:
            merged[-1]["end"] = w["end"]
            merged[-1]["words"].append(w["word"])
        else:
            merged.append({
                "start_seconds": w["start"],
                "end_seconds":   w["end"],
                "words":         [w["word"]],
            })
    return [{
        "start": format_time(m["start_seconds"]),
        "end":   format_time(m["end_seconds"]),
        "duration": round(m["end_seconds"] - m["start_seconds"], 3),
        "removed_text": " ".join(m["words"]),
    } for m in merged]

def save_dual_outputs(segments):
    subtitles, cuts = [], []
    for seg in segments:
        kept, cut = split_words_by_filter(seg)
        sub = build_subtitle_segment(seg, kept)
        if sub:
            subtitles.append(sub)
        cuts.extend(build_cut_entries(cut))

    with open(SUBTITLE_JSON, "w", encoding="utf-8") as f:
        json.dump(subtitles, f, ensure_ascii=False, indent=2)
    with open(CUTS_JSON, "w", encoding="utf-8") as f:
        json.dump(cuts, f, ensure_ascii=False, indent=2)
    print(f"{SUBTITLE_JSON} / {CUTS_JSON} 저장 완료!")    

def main():
    # 입력 파일 존재 여부 확인
    if not os.path.exists(INPUT_VIDEO):
        print(f"오류: {INPUT_VIDEO} 파일이 없습니다.")
        return

    print("영상 확인 완료")

    try:
        # Whisper 모델 로드 후 전사 수행
        print("Whisper 모델 로딩 중...")
        model = whisper.load_model(MODEL_SIZE)

        print("음성 인식 시작...")
        result = model.transcribe(
            INPUT_VIDEO,
            language=LANGUAGE,
            fp16=False,
            word_timestamps = True
        )

    except Exception as e:
        # 모델 로딩/전사 중 오류 처리
        print(f"오류 발생: {e}")
        return

    print("\n[원본 텍스트]")
    print(result["text"])

    print("\nJSON 생성 중...")
    save_dual_outputs(result["segments"])


if __name__ == "__main__":
    main()
