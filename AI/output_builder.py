from typing import Any, Optional


def format_time(seconds: float) -> str:
    """초 단위 시간을 HH:MM:SS 문자열로 변환합니다."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


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
        is_close = merged and word["start"] - merged[-1]["end_seconds"] <= 0.05

        if is_same_reason and is_close:
            merged[-1]["end_seconds"] = word["end"]
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
