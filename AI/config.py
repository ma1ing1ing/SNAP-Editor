from pathlib import Path


DEFAULT_STOPWORD_MODE = "default"
INPUT_JSON = "input/stt_result.json"
SUBTITLE_JSON = "output/subtitles.json"
CUTS_JSON = "output/cut.json"
STOPWORDS_PATH = Path(__file__).parent / "stopwords_ko.json"
