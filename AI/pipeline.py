from typing import Any, Callable, Optional

try:
    from AI.output_builder import build_cut_entries, build_subtitle_segment
    from AI.text_filter import filter_text
except ModuleNotFoundError:
    from output_builder import build_cut_entries, build_subtitle_segment
    from text_filter import filter_text


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


def generate_cut_points(
    segments: list[dict[str, Any]],
    stopwords: list[str],
    target_pos: list[str],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """segment 목록을 받아 자막용 subtitles와 컷 편집용 cut_points를 생성합니다."""
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
