# =============================================================
# SNAP Editor - AI compatibility pipeline
#
# AI 팀의 불용어 필터링 기능은 FE 처리로 이전되어 제거되었습니다.
# 다만 BE에서 기존처럼 `from AI.main import run_ai_pipeline`을 import하므로,
# 다른 팀 코드가 깨지지 않도록 동일한 함수명과 반환 구조만 유지합니다.
# =============================================================

import json
import os
from typing import Any, Callable, Optional


DEFAULT_STOPWORD_MODE = "default"
INPUT_JSON = "input/stt_result.json"
SUBTITLE_JSON = "output/subtitles.json"
CUTS_JSON = "output/cut.json"


def _format_time(seconds: float) -> str:
    """초 단위 시간을 HH:MM:SS 문자열로 변환합니다."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


def _build_subtitles(stt_result: dict[str, Any]) -> list[dict[str, str]]:
    """
    BE 호환용 자막 목록을 생성합니다.
    불용어 제거는 수행하지 않고 STT segment의 원문을 그대로 전달합니다.
    """
    subtitles = []

    for segment in stt_result.get("segments", []):
        start = segment.get("start")
        end = segment.get("end")
        text = str(segment.get("text", "")).strip()

        if start is None or end is None or not text:
            continue

        subtitles.append({
            "start": _format_time(float(start)),
            "end": _format_time(float(end)),
            "text": text,
        })

    return subtitles


def run_ai_pipeline(
    video_path: str,
    params: dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> dict[str, Any]:
    """
    BE 호환용 진입점입니다.
    FE에서 불용어 필터링을 담당하므로 AI cut_points는 생성하지 않습니다.
    """
    mode = params.get("mode", DEFAULT_STOPWORD_MODE)
    stt_result = params.get("stt_result", {})

    if progress_callback:
        progress_callback(0)

    result = {
        "video_path": video_path,
        "mode": mode,
        "subtitles": _build_subtitles(stt_result),
        "cut_points": [],
    }

    if progress_callback:
        progress_callback(100)

    return result


def save_dual_outputs(segments: list[dict[str, Any]], mode: str = DEFAULT_STOPWORD_MODE) -> dict[str, Any]:
    """
    로컬 호환용 저장 함수입니다.
    불용어 컷 결과는 생성하지 않으므로 output/cut.json에는 빈 배열이 저장됩니다.
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


def main() -> None:
    """python AI/main.py로 실행할 때 사용하는 로컬 호환 테스트 함수입니다."""
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
    print("AI 호환 결과 생성 중...")
    save_dual_outputs(stt_result["segments"])


if __name__ == "__main__":
    main()
