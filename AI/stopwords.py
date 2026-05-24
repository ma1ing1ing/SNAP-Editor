import json

try:
    from AI.config import DEFAULT_STOPWORD_MODE, STOPWORDS_PATH
except ModuleNotFoundError:
    from config import DEFAULT_STOPWORD_MODE, STOPWORDS_PATH


def load_stopwords(mode: str = DEFAULT_STOPWORD_MODE) -> tuple[list[str], list[str]]:
    """stopwords_ko.json에서 선택한 모드의 불용어와 대상 품사를 불러옵니다."""
    if not STOPWORDS_PATH.exists():
        raise FileNotFoundError(f"{STOPWORDS_PATH} 파일이 없습니다.")

    with open(STOPWORDS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    modes = data.get("modes", {})
    cfg = modes.get(mode, modes.get(DEFAULT_STOPWORD_MODE, {"words": [], "target_pos": ["IC"]}))

    return cfg.get("words", []), cfg.get("target_pos", ["IC"])
