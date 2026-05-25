import re
from typing import Any, Optional

from kiwipiepy import Kiwi


# Kiwi 객체 생성 비용이 있으므로 모듈 로딩 시 한 번만 초기화합니다.
kiwi = Kiwi()


def normalize_word(word: str) -> str:
    """비교용 단어에서 문장부호와 공백을 제거합니다."""
    return re.sub(r"[^\w가-힣]", "", word).strip()


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
    """사전 매칭과 Kiwi 품사 검증을 모두 통과한 단어를 불용어로 판단합니다."""
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
    _ = segment_time

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
