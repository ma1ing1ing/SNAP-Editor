import os
import re
import whisper

os.environ["PATH"] += os.pathsep + r"D:\ffmpeg\ffmpeg-8.1-essentials_build\bin"

INPUT_VIDEO = "input.mp4"
OUTPUT_SRT = "output.srt"

MODEL_SIZE = "medium"   # tiny, base, small, medium, large
LANGUAGE = "ko"

FILLER_WORDS = ["어", "음", "아", "그", "어어", "음음"]

MAX_WORDS_PER_LINE = 6

MIN_DURATION = 0.3

def normalize_word(word: str) -> str:
    """비교용 단어 정리: 문장부호 제거"""
    return re.sub(r"[^\w가-힣]", "", word).strip()


def remove_filler_words(text: str) -> str:
    """대표적인 추임새 제거 (문장부호 포함 대응)"""
    words = text.split()
    result = []

    for w in words:
        cleaned = normalize_word(w)
        if cleaned and cleaned not in FILLER_WORDS:
            result.append(w)

    return " ".join(result)


def remove_repeated_words(text: str) -> str:
    """같은 단어가 연속 반복될 때 하나만 남김"""
    words = text.split()
    if not words:
        return text

    cleaned_words = [words[0]]

    for w in words[1:]:
        prev = normalize_word(cleaned_words[-1])
        curr = normalize_word(w)

        if curr != prev:
            cleaned_words.append(w)

    return " ".join(cleaned_words)


def clean_text(text: str) -> str:

    text = text.strip()

    # 공백 정리
    text = re.sub(r"\s+", " ", text)

    # 추임새 제거
    text = remove_filler_words(text)

    # 반복 단어 제거
    text = remove_repeated_words(text)

    # 다시 공백 정리
    text = re.sub(r"\s+", " ", text).strip()

    return text


def split_subtitle_lines(text: str, max_words: int = 6) -> str:
    words = text.split()
    lines = []

    for i in range(0, len(words), max_words):
        line = " ".join(words[i:i + max_words])
        lines.append(line)

    return "\n".join(lines)


def format_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def make_srt(segments) -> str:
    srt_lines = []
    subtitle_index = 1

    for seg in segments:
        start = float(seg["start"])
        end = float(seg["end"])
        raw_text = seg["text"]

        cleaned = clean_text(raw_text)

        if not cleaned:
            continue

        if end - start < MIN_DURATION:
            continue

        final_text = split_subtitle_lines(cleaned, MAX_WORDS_PER_LINE)

        srt_lines.append(str(subtitle_index))
        srt_lines.append(f"{format_time(start)} --> {format_time(end)}")
        srt_lines.append(final_text)
        srt_lines.append("")

        subtitle_index += 1

    return "\n".join(srt_lines)

if not os.path.exists(INPUT_VIDEO):
    print(f"오류: {INPUT_VIDEO} 파일이 현재 폴더에 없습니다.")
    raise SystemExit

print("입력 영상 확인 완료")

try:
    print(f"Whisper 모델 로딩 중: {MODEL_SIZE}")
    model = whisper.load_model(MODEL_SIZE)

    print("음성 인식 시작...")
    result = model.transcribe(
        INPUT_VIDEO,
        language=LANGUAGE,
        fp16=False,
        verbose=True
    )

except Exception as e:
    print(f"오류 발생: {e}")
    raise SystemExit

print("\n[원본 변환 텍스트]\n")
print(result["text"])


print("\n자막 후처리 및 SRT 생성 중...")
srt_text = make_srt(result["segments"])

if not srt_text.strip():
    print("경고: 생성된 자막 내용이 없습니다.")
else:
    with open(OUTPUT_SRT, "w", encoding="utf-8") as f:
        f.write(srt_text)
    print(f"{OUTPUT_SRT} 파일 저장 완료!")