import json
from main import run_ai_pipeline

sample_stt_result = {
    "segments": [
        {
            "start": 1.2,
            "end": 3.5,
            "text": "음 저는 저는 그렇게 생각합니다",
            "words": [
                {"word": "음", "start": 1.2, "end": 1.4},
                {"word": "저는", "start": 1.4, "end": 1.8},
                {"word": "저는", "start": 1.8, "end": 2.1},
                {"word": "그렇게", "start": 2.1, "end": 2.8},
                {"word": "생각합니다", "start": 2.8, "end": 3.5}
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

result = run_ai_pipeline(
    video_path="sample.mp4",
    params={
        "mode": "default",
        "stt_result": sample_stt_result
    }
)

print(json.dumps(result, ensure_ascii=False, indent=2))