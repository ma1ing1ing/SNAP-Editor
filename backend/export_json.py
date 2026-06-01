import json
import os

import librosa
import numpy as np
import torch


_SILERO_MODEL = None
_SILERO_UTILS = None


def _emit(callback, value):
    if callback:
        callback(value)


def _load_silero_vad(log_callback=None):
    """Silero VAD 모델을 한 번만 로드해서 같은 실행 안에서 재사용합니다."""
    global _SILERO_MODEL, _SILERO_UTILS

    if _SILERO_MODEL is None or _SILERO_UTILS is None:
        _emit(log_callback, "Silero VAD 모델 로드 중... 첫 실행은 시간이 걸릴 수 있습니다.")
        _SILERO_MODEL, _SILERO_UTILS = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            trust_repo=True,
        )

    return _SILERO_MODEL, _SILERO_UTILS


def detect_silence(audio_path, min_silence_seconds=1.0, progress_callback=None, log_callback=None):
    """
    오디오 파일에서 음성/무음 구간을 탐지합니다.
    progress_callback은 backend_controller 기준 40~80 사이의 세부 진행률을 전달합니다.
    """
    if not os.path.exists(audio_path):
        return [], {}

    _emit(progress_callback, 45)
    model, utils = _load_silero_vad(log_callback)
    (get_speech_timestamps, _, _, _, _) = utils

    _emit(log_callback, "오디오 파일 로드 중...")
    y_original, sr_original = librosa.load(audio_path, sr=None)
    duration = len(y_original) / sr_original
    _emit(progress_callback, 55)

    _emit(log_callback, "VAD 분석용 16kHz 리샘플링 중...")
    y_16k = librosa.resample(y_original, orig_sr=sr_original, target_sr=16000)
    audio_tensor = torch.from_numpy(y_16k)
    _emit(progress_callback, 65)

    _emit(log_callback, "음성/무음 구간 탐지 중...")
    speech_timestamps = get_speech_timestamps(
        audio_tensor,
        model,
        sampling_rate=16000,
        threshold=0.5,
        min_silence_duration_ms=int(min_silence_seconds * 1000),
    )
    _emit(progress_callback, 75)

    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    results = {
        "video_info": {"file_name": f"{base_name}.webm", "total_duration": round(duration, 2)},
        "speech_segments": [],
        "silence_segments": [],
    }

    silence_return_list = []
    current_last_pos = 0.0
    silence_id = 1

    for idx, timestamp in enumerate(speech_timestamps):
        start_sec = round(timestamp["start"] / 16000, 2)
        end_sec = round(timestamp["end"] / 16000, 2)

        results["speech_segments"].append({
            "id": idx + 1,
            "start": start_sec,
            "end": end_sec,
            "duration": round(end_sec - start_sec, 2),
        })

        if start_sec - current_last_pos > 0.1:
            silence_start = round(current_last_pos, 2)
            silence_end = start_sec

            results["silence_segments"].append({
                "id": silence_id,
                "start": silence_start,
                "end": silence_end,
                "duration": round(silence_end - silence_start, 2),
            })
            silence_return_list.append((silence_start, silence_end))
            silence_id += 1

        current_last_pos = end_sec

    if duration - current_last_pos > 0.1:
        silence_start = round(current_last_pos, 2)
        silence_end = round(duration, 2)

        results["silence_segments"].append({
            "id": silence_id,
            "start": silence_start,
            "end": silence_end,
            "duration": round(silence_end - silence_start, 2),
        })
        silence_return_list.append((silence_start, silence_end))

    _emit(progress_callback, 80)
    return silence_return_list, results


if __name__ == "__main__":
    video_file = "Data/test_video.mp4"
    silence_list, detailed_json_data = detect_silence(video_file)
    print("프론트로 보낼 튜플 리스트:", silence_list)
    print("\n상세 JSON 데이터:", json.dumps(detailed_json_data, ensure_ascii=False, indent=2))
