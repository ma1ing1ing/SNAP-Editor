import re
import json
from pathlib import Path
from kiwipiepy import Kiwi


# stopwords_ko.json 파일 위치
STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"

# 기본 불용어 모드
DEFAULT_STOPWORD_MODE = "default"

# Kiwi 형태소 분석기 생성
kiwi = Kiwi()


# 불용어 설정 불러오기
def load_stopwords(mode: str = DEFAULT_STOPWORD_MODE):
    """
    stopwords_ko.json에서 선택한 모드의 불용어 단어와 품사 정보를 불러온다.
    mode 값이 없거나 잘못 들어오면 default 모드를 사용한다.
    """

    if not STOPWORDS_PATH.exists():
        raise FileNotFoundError(f"{STOPWORDS_PATH} 파일이 없습니다.")

    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    cfg = data["modes"].get(mode, data["modes"]["default"])

    return cfg["words"], cfg["target_pos"]


# 시간 표시 형식 변환
def format_time(seconds: float) -> str:
    """
    초 단위 시간을 00:00:00 형식으로 변환한다.
    예: 65.3초 -> 00:01:05
    """

    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    return f"{hours:02}:{minutes:02}:{secs:02}"


# 단어 정규화
def normalize_word(word: str) -> str:
    """
    단어에서 특수문자나 불필요한 공백을 제거한다.
    예: '어,' -> '어'
    """

    return re.sub(r"[^\w가-힣]", "", word).strip()


# 불용어 여부 판별
def classify_stopword(word: str, stopword_words, target_pos) -> bool:
    """
    입력된 단어가 불용어인지 판별한다.

    판별 기준:
    1. 단어를 정규화한다.
    2. stopwords_ko.json에 등록된 단어인지 확인한다.
    3. Kiwi 형태소 분석 결과가 target_pos에 해당하는지 확인한다.
    """

    clean_word = normalize_word(word)

    if not clean_word:
        return False

    if clean_word not in stopword_words:
        return False

    tokens = kiwi.tokenize(clean_word)

    for token in tokens:
        if token.form == clean_word and token.tag in target_pos:
            return True

    return False


# STT 결과에서 단어 정보 추출
def extract_words(stt_result: dict):
    """
    백엔드 또는 STT 모듈에서 전달받은 결과에서
    word, start, end 정보를 가진 단어만 추출한다.
    """

    all_words = []

    segments = stt_result.get("segments", [])

    for seg in segments:
        words = seg.get("words", [])

        for w in words:
            if "word" not in w or "start" not in w or "end" not in w:
                continue

            all_words.append({
                "word": w["word"],
                "start": float(w["start"]),
                "end": float(w["end"])
            })

    return all_words


# AI 메인 파이프라인
def run_ai_pipeline(stt_result: dict, params: dict = None, progress_callback=None):
    """
    STT 결과를 기반으로 불용어만 탐지하는 함수

    입력 예시:
    stt_result = {
        "segments": [
            {
                "words": [
                    {
                        "word": "어",
                        "start": 1.2,
                        "end": 1.5
                    }
                ]
            }
        ]
    }

    반환 예시:
    {
        "cut_points": [
            {
                "start": "00:00:01",
                "end": "00:00:01",
                "start_seconds": 1.2,
                "end_seconds": 1.5,
                "duration": 0.3,
                "removed_text": "어",
                "reason": "stopword"
            }
        ]
    }
    """

    if params is None:
        params = {}

    # 사용할 불용어 모드 선택
    stopword_mode = params.get("stopword_mode", DEFAULT_STOPWORD_MODE)

    # 불용어 단어 목록과 검사할 품사 목록 불러오기
    stopword_words, target_pos = load_stopwords(stopword_mode)

    # STT 결과에서 단어 목록 추출
    all_words = extract_words(stt_result)
    total = len(all_words)

    cut_points = []

    # 단어가 없을 경우 빈 결과 반환
    if total == 0:
        if progress_callback:
            progress_callback(100)

        return {
            "cut_points": []
        }

    # 단어별 불용어 판별
    for idx, w in enumerate(all_words):
        word = w["word"].strip()
        start_seconds = w["start"]
        end_seconds = w["end"]

        if classify_stopword(word, stopword_words, target_pos):
            cut_points.append({
                "start": format_time(start_seconds),
                "end": format_time(end_seconds),
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration": round(end_seconds - start_seconds, 3),
                "removed_text": word,
                "reason": "stopword"
            })

        # 진행률 콜백
        if progress_callback:
            progress = int((idx + 1) / total * 100)
            progress_callback(progress)

    # 시간 순서대로 정렬
    cut_points.sort(key=lambda x: x["start_seconds"])

    return {
        "cut_points": cut_points
    }


# 단독 테스트용 코드
if __name__ == "__main__":
    sample_stt_result = {
        "segments": [
            {
                "words": [
                    {
                        "word": "어",
                        "start": 1.2,
                        "end": 1.5
                    },
                    {
                        "word": "안녕하세요",
                        "start": 1.6,
                        "end": 2.3
                    },
                    {
                        "word": "음",
                        "start": 2.4,
                        "end": 2.7
                    }
                ]
            }
        ]
    }

    def print_progress(value):
        print(f"진행률: {value}%")

    result = run_ai_pipeline(
        sample_stt_result,
        params={"stopword_mode": "default"},
        progress_callback=print_progress
    )

    print(json.dumps(result, ensure_ascii=False, indent=2))
