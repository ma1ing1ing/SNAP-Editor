# =============================================================
# SNAP Editor - AI filter main pipeline (Python 3.10)
#
# [목적]
#   BE는 run_ai_pipeline()을 import해서 STT 결과를 바로 넘겨줄 수 있습니다.
#   이 파일을 직접 실행하는 경우는 로컬 JSON 파일 테스트용입니다.
#
# [처리 흐름]
#   1. 불용어 설정 로드       : stopwords_ko.json + load_stopwords
#   2. STT segment 정리       : parse_stt_result
#   3. 1차 사전 매칭          : pass_first_filter
#   4. 2차 품사 검증          : pass_second_filter (Kiwi)
#   5. 단어 단위 분리         : filter_text
#      - 불용어 제거
#      - 반복 단어 제거
#   6. 결과 생성              : subtitles + cut_points
#
# [BE 호출 입력]
#   run_ai_pipeline(video_path, params, progress_callback=None)
#
#   params = {
#       "mode": "default",
#       "stt_result": {
#           "segments": [
#               {
#                   "start": 1.2,
#                   "end": 3.5,
#                   "text": "...",
#                   "words": [
#                       {"word": "음", "start": 1.2, "end": 1.4}
#                   ]
#               }
#           ]
#       }
#   }
#
# [BE 호출 반환]
#   {
#       "video_path": "...",
#       "mode": "default",
#       "subtitles": [...],
#       "cut_points": [...]
#   }
#
# [로컬 테스트 입출력]
#   입력 : input/stt_result.json
#   출력 : output/subtitles.json, output/cut.json
# =============================================================

import json
import os
import re
from pathlib import Path
from typing import Any, Callable, Optional

from kiwipiepy import Kiwi

# 아래 파일 경로들은 main.py를 직접 실행해 로컬 테스트할 때만 사용합니다.
# 실제 BE 연동에서는 run_ai_pipeline()의 반환값을 사용하므로 파일 저장이 필수는 아닙니다.
DEFAULT_STOPWORD_MODE = "default"
INPUT_JSON = "input/stt_result.json"
SUBTITLE_JSON = "output/subtitles.json"
CUTS_JSON = "output/cut.json"
STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"

# Kiwi 객체 생성 비용이 있으므로 모듈 로딩 시 한 번만 초기화합니다.
kiwi = Kiwi()


def format_time(seconds: float) -> str:
    """초 단위 시간을 HH:MM:SS 문자열로 변환합니다."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


def normalize_word(word: str) -> str:
    """비교용 단어에서 문장부호와 공백을 제거합니다."""
    return re.sub(r"[^\w가-힣]", "", word).strip()


def load_stopwords(mode: str = DEFAULT_STOPWORD_MODE) -> tuple[list[str], list[str]]:
    """stopwords_ko.json에서 선택한 모드의 불용어와 대상 품사를 불러옵니다."""
    if not STOPWORDS_PATH.exists():
        raise FileNotFoundError(f"{STOPWORDS_PATH} 파일이 없습니다.")

    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    modes = data.get("modes", {})
    cfg = modes.get(mode, modes.get(DEFAULT_STOPWORD_MODE, {"words": [], "target_pos": ["IC"]}))

    return cfg.get("words", []), cfg.get("target_pos", ["IC"])


def parse_stt_result(stt_result: dict[str, Any]) -> list[dict[str, Any]]:
    """
    BE 또는 STT 모듈이 넘겨준 원본 STT 결과를 AI 처리용 segment 목록으로 정리합니다.
    start/end가 없는 segment는 컷 구간을 계산할 수 없으므로 제외합니다.
    """
    parsed_segments = []

    for segment in stt_result.get("segments", []):
        start = segment.get("start")
        end = segment.get("end")

        if start is None or end is None:
            continue

        parsed_segments.append({
            "start": float(start),
            "end": float(end),
            "text": segment.get("text", ""),
            "words": segment.get("words", []),
        })

    return parsed_segments


def pass_first_filter(word: str, stopwords: list[str]) -> bool:
    """1차 필터: 정규화한 단어가 불용어 사전에 있는지 확인합니다."""
    return normalize_word(word) in stopwords


def pass_second_filter(word: str, target_pos: list[str]) -> bool:
    """2차 필터: Kiwi 품사 분석 결과가 대상 품사인지 확인합니다."""
    clean = normalize_word(word)

    if not clean:
        return False

    tokens = kiwi.tokenize(clean)

    for token in tokens:
        if token.form == clean and token.tag in target_pos:
            return True

    return False


def classify_filler(word: str, stopwords: list[str], target_pos: list[str]) -> bool:
    """
    불용어 후보인지 판정합니다.
    사전 매칭을 먼저 하고, 통과한 단어만 Kiwi 품사 검증을 수행합니다.
    """
    if not pass_first_filter(word, stopwords):
        return False

    return pass_second_filter(word, target_pos)

def decide_cut(
    original_text: str,
    cleaned_text: str,
    segment_time: tuple[float, float],
    stopwords: list[str],
    target_pos: list[str],
    prev_kept_norm: Optional[str] = None,
) -> str:
    """
    단어를 유지할지 제거할지 결정합니다.
    반환값은 명세서에 맞춰 "keep" 또는 "remove"를 사용합니다.
    """
    if classify_filler(original_text, stopwords, target_pos):
        return "remove"

    if cleaned_text and cleaned_text == prev_kept_norm:
        return "remove"

    return "keep"



def parse_word_token(word_info: dict[str, Any]) -> Optional[dict[str, Any]]:
    """STT word 객체를 word/start/end 형태로 정리합니다. 필수 값이 없으면 제외합니다."""
    word = str(word_info.get("word", "")).strip()
    start = word_info.get("start")
    end = word_info.get("end")

    if not word or start is None or end is None:
        return None

    return {
        "word": word,
        "start": float(start),
        "end": float(end),
    }


def filter_text(
    words: list[dict[str, Any]],
    stopwords: list[str],
    target_pos: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    단어 타임스탬프를 기준으로 유지할 단어와 제거할 단어를 분리합니다.
    컷 편집 정확도를 위해 segment 전체 시간이 아니라 각 word의 start/end를 사용합니다.
    """
    kept_words = []
    cut_words = []
    prev_kept_norm = None

    for word_info in words:
        token = parse_word_token(word_info)

        if token is None:
            continue

        curr_norm = normalize_word(token["word"])

        action = decide_cut(
            original_text=token["word"],
            cleaned_text=curr_norm,
            segment_time=(token["start"], token["end"]),
            stopwords=stopwords,
            target_pos=target_pos,
            prev_kept_norm=prev_kept_norm,
        )

        if action == "remove":
            reason = "filler" if classify_filler(token["word"], stopwords, target_pos) else "repeated"
            cut_words.append({**token, "reason": reason})
            continue

        kept_words.append(token)
        prev_kept_norm = curr_norm

    return kept_words, cut_words


def build_subtitle_segment(segment: dict[str, Any], kept_words: list[dict[str, Any]]) -> Optional[dict[str, str]]:
    """제거되지 않은 단어들로 자막용 segment를 만듭니다."""
    if not kept_words:
        return None

    return {
        "start": format_time(kept_words[0]["start"]),
        "end": format_time(kept_words[-1]["end"]),
        "text": " ".join(word["word"] for word in kept_words),
    }


def build_cut_entries(cut_words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """서로 붙어 있는 제거 단어들을 하나의 컷 구간으로 병합합니다."""
    merged = []

    for word in cut_words:
        is_same_reason = merged and word["reason"] == merged[-1]["reason"]
        is_close = merged and word["start"] - merged[-1]["end"] <= 0.05

        if is_same_reason and is_close:
            merged[-1]["end"] = word["end"]
            merged[-1]["words"].append(word["word"])
        else:
            merged.append({
                "start_seconds": word["start"],
                "end_seconds": word["end"],
                "words": [word["word"]],
                "reason": word["reason"],
            })

    return [{
        "start": format_time(entry["start_seconds"]),
        "end": format_time(entry["end_seconds"]),
        "start_seconds": entry["start_seconds"],
        "end_seconds": entry["end_seconds"],
        "duration": round(entry["end_seconds"] - entry["start_seconds"], 3),
        "removed_text": " ".join(entry["words"]),
        "reason": entry["reason"],
    } for entry in merged]

def generate_cut_points(
    segments: list[dict[str, Any]],
    stopwords: list[str],
    target_pos: list[str],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """
    segment 목록을 받아 자막용 subtitles와 컷 편집용 cut_points를 생성합니다.
    """
    subtitles = []
    cut_points = []
    total = len(segments)

    if total == 0:
        if progress_callback:
            progress_callback(100)
        return subtitles, cut_points

    for idx, segment in enumerate(segments):
        kept_words, cut_words = filter_text(
            segment.get("words", []),
            stopwords,
            target_pos,
        )

        subtitle = build_subtitle_segment(segment, kept_words)
        if subtitle:
            subtitles.append(subtitle)

        cut_points.extend(build_cut_entries(cut_words))

        if progress_callback:
            progress_callback(int(((idx + 1) / total) * 100))

    return subtitles, cut_points

# BE에서 호출하는 메인 함수.
# video_path와 STT 결과를 받아 자막용 데이터와 컷 편집용 데이터를 반환합니다.
# 이 함수 안에서는 파일 저장을 하지 않습니다.
def run_ai_pipeline(
    video_path: str,
    params: dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> dict[str, Any]:
    mode = params.get("mode", DEFAULT_STOPWORD_MODE)
    stt_result = params.get("stt_result", {})

    if progress_callback:
        progress_callback(0)

    stopwords, target_pos = load_stopwords(mode)
    segments = parse_stt_result(stt_result)

    subtitles, cut_points = generate_cut_points(
        segments=segments,
        stopwords=stopwords,
        target_pos=target_pos,
        progress_callback=progress_callback,
    )

    return {
        "video_path": video_path,
        "mode": mode,
        "subtitles": subtitles,
        "cut_points": cut_points,
    }

# 로컬 테스트용 함수.
# run_ai_pipeline() 결과를 output/subtitles.json, output/cut.json으로 저장한다.
# 실제 BE 연동에서는 이 함수를 호출하지 않아도 된다.
def save_dual_outputs(segments: list[dict[str, Any]], mode: str = DEFAULT_STOPWORD_MODE) -> dict[str, Any]:
    """
    로컬 테스트용 저장 함수입니다.
    실제 BE 연동에서는 run_ai_pipeline()의 반환값을 그대로 사용하면 됩니다.
    """
    os.makedirs("output", exist_ok=True)

    result = run_ai_pipeline(
        video_path="",
        params={
            "mode": mode,
            "stt_result": {"segments": segments},
        },
    )

    with open(SUBTITLE_JSON, "w", encoding="utf-8") as f:
        json.dump(result["subtitles"], f, ensure_ascii=False, indent=2)

    with open(CUTS_JSON, "w", encoding="utf-8") as f:
        json.dump(result["cut_points"], f, ensure_ascii=False, indent=2)

    print(f"{SUBTITLE_JSON} / {CUTS_JSON} 저장 완료")
    return result

# main.py를 직접 실행할 때만 사용하는 테스트 코드.
# BE에서 import할 때는 실행되지 않는다.
def main() -> None:
    """python AI/main.py로 실행할 때 사용하는 로컬 테스트 함수입니다."""
    if not os.path.exists(INPUT_JSON):
        print(f"오류: {INPUT_JSON} 파일이 없습니다.")
        return

    try:
        with open(INPUT_JSON, "r", encoding="utf-8") as f:
            stt_result = json.load(f)
    except Exception as exc:
        print(f"JSON 읽기 오류: {exc}")
        return

    if "segments" not in stt_result:
        print("오류: JSON 파일에 segments 필드가 없습니다.")
        return

    print("STT 결과 JSON 확인 완료")
    print("AI 필터 결과 생성 중...")
    save_dual_outputs(stt_result["segments"])

# 직접 실행할 때만 로컬 테스트를 수행한다.
# BE에서 import할 때는 실행되지 않고, python AI/main.py로 직접 실행할 때만 동작합니다.
if __name__ == "__main__":
    main()
