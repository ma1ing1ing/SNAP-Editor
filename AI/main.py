# =============================================================
# SNAP Editor - AI filter main pipeline (Python 3.10)
#
# [AI 단독 테스트]
#   샘플 테스트: cd AI && python test_ai_pipeline.py
#   JSON 테스트: 프로젝트 루트에서 python AI/main.py
#   JSON 테스트 입력: input/stt_result.json
#   JSON 테스트 출력: output/subtitles.json, output/cut.json
#
# BE는 이 파일의 run_ai_pipeline()만 import해서 사용합니다.
# 내부 기능은 stopwords.py, text_filter.py, output_builder.py, pipeline.py로 분리되어 있습니다.
# =============================================================

import json
import os
from typing import Any, Callable, Optional

try:
    from AI.config import CUTS_JSON, DEFAULT_STOPWORD_MODE, INPUT_JSON, SUBTITLE_JSON
    from AI.pipeline import generate_cut_points, parse_stt_result
    from AI.stopwords import load_stopwords
except ModuleNotFoundError:
    from config import CUTS_JSON, DEFAULT_STOPWORD_MODE, INPUT_JSON, SUBTITLE_JSON
    from pipeline import generate_cut_points, parse_stt_result
    from stopwords import load_stopwords


def run_ai_pipeline(
    video_path: str,
    params: dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None,
) -> dict[str, Any]:
    """
    BE에서 호출하는 메인 함수입니다.
    STT 결과를 받아 자막용 subtitles와 컷 편집용 cut_points를 반환합니다.
    """
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


if __name__ == "__main__":
    main()
