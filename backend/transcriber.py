import os
import threading
import time

import stable_whisper as ststable
from kiwipiepy import Kiwi


def format_time(seconds):
    seconds = max(0.0, seconds)
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def transcribe_video_to_srt(
    video_path,
    output_srt_path="./backend/Data/subtitle.srt",
    model_size="small",
    status_callback=None,
    progress_callback=None,
):
    def emit_status(msg):
        if status_callback:
            status_callback(msg)

    def emit_progress(value):
        if progress_callback:
            progress_callback(value)

    def start_transcribe_progress():
        """
        stable-ts does not expose detailed progress from transcribe().
        This heartbeat keeps the UI moving while STT is still running.
        """
        stop_event = threading.Event()

        def worker():
            progress = 31
            started_at = time.time()
            while not stop_event.wait(8):
                elapsed = int(time.time() - started_at)
                emit_status(f"자막 생성 중... {elapsed // 60:02}:{elapsed % 60:02} 경과")
                emit_progress(progress)
                if progress < 65:
                    progress += 1

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        return stop_event

    emit_status("자막 생성을 준비하는 중...")
    emit_progress(10)
    print(f"\n[STT] stable-ts transcription started: {video_path} (model: {model_size})")

    model = ststable.load_model(model_size)
    kiwi = Kiwi()

    emit_status("자막 변환 중...\n영상 길이에 따라 몇 분 걸릴 수 있습니다.")
    emit_progress(30)

    transcribe_progress = start_transcribe_progress()
    try:
        result = model.transcribe(
            video_path,
            language="ko",
            word_timestamps=True,
            vad=True,
        )
    finally:
        transcribe_progress.set()

    result = (
        result
        .split_by_punctuation([".", "\u3002", "?", "\uff1f", "!", "\uff01"])
        .split_by_gap(0.8)
        .merge_by_gap(0.3, max_words=5)
        .split_by_length(max_chars=60, max_words=18)
    )

    detected_lang = result.language
    emit_status("자막을 정리하는 중...")
    emit_progress(70)
    print(f"[STT] detected language: {detected_lang}")

    with open(output_srt_path, "w", encoding="utf-8") as srt_file:
        for i, segment in enumerate(result.segments, start=1):
            text = segment.text.strip()
            if not text:
                continue

            if detected_lang == "ko" and not text.endswith((".", "?", "!")):
                tokens = kiwi.tokenize(text)
                if tokens:
                    last_tag = tokens[-1].tag
                    if last_tag.startswith("EF") or text[-1] in ["\ub2e4", "\uc694", "\uae4c", "\uc8e0"]:
                        text += "."

            delay_offset = 0.15
            start_time = format_time(segment.start + delay_offset)
            end_time = format_time(segment.end + delay_offset)
            srt_file.write(f"{i}\n{start_time} --> {end_time}\n{text}\n\n")

    print(f"[STT] subtitle file created: {output_srt_path}")

    stt_result = {"segments": []}
    for segment in result.segments:
        words_list = []

        if hasattr(segment, "words") and segment.words:
            for word in segment.words:
                words_list.append({
                    "word": word.word,
                    "start": word.start,
                    "end": word.end,
                })

        stt_result["segments"].append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text.strip(),
            "words": words_list,
        })

    return output_srt_path, detected_lang, stt_result
