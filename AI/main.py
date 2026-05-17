import re
import json
from pathlib import Path
from typing import Dict, List, Any, Callable, Optional
from kiwipiepy import Kiwi


STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"
DEFAULT_STOPWORD_MODE = "default"

kiwi = Kiwi()


# 초 단위 시간을 00:00:00 형식으로 변환
def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


# 단어에서 특수문자 제거
def normalize_word(word: str) -> str:
    return re.sub(r"[^\w가-힣]", "", word)


# stopwords_ko.json에서 불용어 설정 불러오기
def load_stopwords(mode: str = DEFAULT_STOPWORD_MODE):
    if not STOPWORDS_PATH.exists():
        raise FileNotFoundError(f"{STOPWORDS_PATH} 파일이 없습니다.")

    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data["modes"].get(mode, data["modes"]["default"])

    return cfg["words"], cfg["target_pos"]


# BE가 넘겨준 STT 결과를 AI가 처리하기 좋은 형태로 정리
def parse_stt_result(stt_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    segments = stt_result.get("segments", [])
    parsed_segments = []

    for segment in segments:
        start = segment.get("start")
        end = segment.get("end")
        text = segment.get("text", "")
        words = segment.get("words", [])

        if start is None or end is None:
            continue

        parsed_segments.append({
            "start": float(start),
            "end": float(end),
            "text": text,
            "words": words
        })

    return parsed_segments


# 불용어 탐지
def detect_stopwords(
    segments: List[Dict[str, Any]],
    mode: str = DEFAULT_STOPWORD_MODE,
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[Dict[str, Any]]:

    stopwords, target_pos = load_stopwords(mode)
    cut_points = []

    total = len(segments)

    if total == 0:
        if progress_callback:
            progress_callback(100)
        return cut_points

    for idx, segment in enumerate(segments):
        text = segment["text"]
        start = segment["start"]
        end = segment["end"]

        tokens = kiwi.tokenize(text)

        for token in tokens:
            word = normalize_word(token.form)
            pos = token.tag

            # 감탄사(IC) 품사이면서 stopwords_ko.json에 등록된 단어만 탐지
            if word in stopwords and pos in target_pos:
                cut_points.append({
                    "start": format_time(start),
                    "end": format_time(end),
                    "start_seconds": start,
                    "end_seconds": end,
                    "duration": round(end - start, 2),
                    "removed_text": word,
                    "reason": "stopword"
                })

        progress = int(((idx + 1) / total) * 100)

        if progress_callback:
            progress_callback(progress)

    return cut_points


# 전체 AI 파이프라인
def run_ai_pipeline(
    video_path: str,
    params: Dict[str, Any],
    progress_callback: Optional[Callable[[int], None]] = None
) -> Dict[str, Any]:

    mode = params.get("mode", DEFAULT_STOPWORD_MODE)
    stt_result = params.get("stt_result", {})

    if progress_callback:
        progress_callback(0)

    segments = parse_stt_result(stt_result)

    cut_points = detect_stopwords(
        segments=segments,
        mode=mode,
        progress_callback=progress_callback
    )

    return {
        "video_path": video_path,
        "mode": mode,
        "cut_points": cut_points
    }


# FE / BE 연결 전 테스트용 코드
if __name__ == "__main__":
    test_stt_result = {
        "segments": [
            {
                "start": 1.2,
                "end": 3.5,
                "text": "음 저는 그렇게 생각합니다",
                "words": [
                    {"word": "음", "start": 1.2, "end": 1.4},
                    {"word": "저는", "start": 1.4, "end": 1.8},
                    {"word": "그렇게", "start": 1.8, "end": 2.6},
                    {"word": "생각합니다", "start": 2.6, "end": 3.5}
                ]
            },
            {
                "start": 5.0,
                "end": 7.3,
                "text": "어 그 부분은 다시 말하겠습니다",
                "words": [
                    {"word": "어", "start": 5.0, "end": 5.2},
                    {"word": "그", "start": 5.2, "end": 5.4},
                    {"word": "부분은", "start": 5.4, "end": 6.0},
                    {"word": "다시", "start": 6.0, "end": 6.5},
                    {"word": "말하겠습니다", "start": 6.5, "end": 7.3}
                ]
            }
        ]
    }

    def progress(percent: int):
        print(f"진행률: {percent}%")

    result = run_ai_pipeline(
        video_path="input.mp4",
        params={
            "mode": "default",
            "stt_result": test_stt_result
        },
        progress_callback=progress
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
