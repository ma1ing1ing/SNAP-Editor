import os
import json
import sys

# 현재 모듈(backend)을 경로에 추가하여 모듈 내 함수들을 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# backend/Data 경로 — 실행 위치에 관계없이 이 파일 기준으로 고정
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data")

from extract_audio import extract_audio
from editor import create_final_edited_video, add_subtitles_to_video
from transcriber import transcribe_video_to_srt
from viewer import display_waveform_with_silence, get_waveform_data

# 🚀 [수정 포인트 1] 기존 vad_tagger 대신, 멘티가 만든 export_json을 임포트!
# from vad_tagger import detect_and_tag_silence (기존 코드는 주석 처리 또는 삭제)
from export_json import detect_silence

class BackendController:
    def __init__(self, progress_callback=None, log_callback=None):
        """
        초기화 시 프론트엔드와 통신할 콜백 함수를 등록합니다.
        :param progress_callback: (int) -> None (0~100의 진행률 업데이트)
        :param log_callback: (str) -> None (로그 메시지 업데이트)
        """
        self.progress_callback = progress_callback
        self.log_callback = log_callback

    def _log(self, message):
        """프론트엔드로 로그 메시지를 전달합니다."""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(message)

    def _progress(self, value):
        """프론트엔드로 진행률(0~100)을 전달합니다."""
        if self.progress_callback:
            self.progress_callback(value)

    def run_step1_extract_and_vad(self, input_video, temp_audio, output_json,
                                   threshold=0.3):
        """
        Step 1: 영상 불러오기, 오디오 추출, VAD 분석, JSON 내보내기
        """
        self._log("▶ [Step 1] 오디오 추출 및 VAD 분석 시작...")
        self._progress(0)

        # 1. 오디오 추출
        self._log(f"오디오 추출 중...: {input_video}")
        self._progress(10)

        success = extract_audio(input_video, temp_audio)
        if not success:
            self._log("❌ 오디오 추출 실패")
            return None

        self._progress(40)

        # 2. VAD 분석 (무음 구간 탐지)
        self._log(f"AI 기반 VAD 무음 구간 분석 중... (threshold={threshold})")
        _, vad_results = detect_silence(temp_audio, min_silence_seconds=threshold)
        silence_segments = vad_results.get("silence_segments", []) if vad_results else []

        self._progress(80)

        # 3. 분석 결과를 JSON 파일로 저장
        self._log("상세 분석 결과 JSON 저장 중...")
        with open(output_json, 'w', encoding='utf-8') as f:
            json.dump(silence_segments, f, indent=4, ensure_ascii=False)

        self._progress(100)
        self._log(f"✅ [Step 1] 완료. 상세 JSON 파일 저장됨: {output_json}")

        # 다음 단계로 넘길 상태(State) 데이터 리턴
        return {
            "temp_audio": temp_audio,
            "json_path": output_json,
            "silence_list": silence_segments
        }
    
    def run_step2_get_waveform_data(self, temp_audio, json_path, num_points=3000):
        """
        프론트엔드에서 파형을 그리기 위한 데이터를 요청할 때 사용합니다.
        """
        self._log("▶ [Step 2] 파형 시각화 뷰어 띄우기 준비...")
        self._progress(0)

        if not os.path.exists(temp_audio) or not os.path.exists(json_path):
            self._log("❌ 에러: 오디오 파일이나 JSON 파일이 존재하지 않습니다. Step 1을 먼저 진행해주세요.")
            return None

        # 저장된 JSON에서 무음 구간 로드
        with open(json_path, 'r', encoding='utf-8') as f:
            silence_list = json.load(f)

        self._log(f"뷰어 창을 로드합니다. ({len(silence_list)}개의 무음 구간 표시)")
        self._progress(50)

        # 될 때까지 블로킹됨
        display_waveform_with_silence(temp_audio, silence_segments=silence_list)

        waveform_data = get_waveform_data(temp_audio, num_points=num_points)
        self._progress(100)
        self._log("✅ 파형 데이터 추출 완료. 프론트엔드로 전송합니다.")
        return waveform_data

    def run_step2_stt(self, video_path, srt_path, whisper_model):
        """
        Step 2: STTWorker에서 호출하는 통합 STT 메서드
        """
        self._log(f"▶ STT 모델({whisper_model}) 로드 중...")
        self._progress(0)
        
        from transcriber import transcribe_video_to_srt
        
        # transcriber를 호출하며 status_callback을 전달
        srt_path, detected_lang, stt_result, ai_result = transcribe_video_to_srt(
            video_path, srt_path, model_size=whisper_model, status_callback=self._log
        )
        
        self._progress(100)
        return stt_result, ai_result

    def run_final_render(self, input_video, segments, output_video):
        """
        프론트엔드에서 수정한 segments를 바로 받아 렌더링하고 자막을 병합하는 최종 메서드
        """
        self._progress(0)
        self._log("▶ [최종 렌더링] 컷편집 영상 렌더링 시작...")
        
        # 1. segments에서 잘라낼 무음 구간만 초(s) 단위로 추출
        silence_segments = [
            {"start": seg["start"] / 1000.0, "end": seg["end"] / 1000.0}
            for seg in segments if not seg.get("keep", True)
        ]
        
        # 2. 영상 컷편집 실행
        temp_edited = os.path.join(_DATA_DIR, "temp_edited.mp4")
        create_final_edited_video(input_video, silence_segments, temp_edited)
        self._progress(50)
        
        # 3. STT를 돌리지 않고, segments에 담긴 텍스트로 즉석에서 SRT 생성
        self._log("▶ 사용자 수정 자막 기반 SRT 생성 중...")
        subtitle_srt = os.path.join(_DATA_DIR, "subtitle.srt")
        from transcriber import format_time
        with open(subtitle_srt, "w", encoding="utf-8") as f:
            new_current_time = 0.0
            subtitle_index = 1
            for seg in segments:
                if seg.get("keep", True):
                    duration = (seg["end"] - seg["start"]) / 1000.0
                    text = seg.get("text", "").strip()
                    if text and text != "(불용어)":
                        start_str = format_time(new_current_time)
                        end_str = format_time(new_current_time + duration)
                        f.write(f"{subtitle_index}\n{start_str} --> {end_str}\n{text}\n\n")
                        subtitle_index += 1
                    new_current_time += duration
                    
        # 4. 컷편집된 영상에 자막 병합
        self._log("▶ 자막 병합 중...")
        success = add_subtitles_to_video(temp_edited, subtitle_srt, output_video, language="ko")
        
        if success:
            self._progress(100)
            self._log(f"✅ 최종 영상 생성 완료: {output_video}")
            
            # 5. 캐싱해두었던 원본 불용어 데이터 불러오기
            cut_points = []
            cached_ai_path = os.path.join(_DATA_DIR, "cached_ai_result.json")
            if os.path.exists(cached_ai_path):
                with open(cached_ai_path, "r", encoding="utf-8") as f:
                    ai_res = json.load(f)
                    cut_points = ai_res.get("cut_points", [])
                
                # 사용 완료된 캐시 파일 삭제
                try:
                    os.remove(cached_ai_path)
                except Exception:
                    pass
                    
            # 6. 용량 절약을 위해 렌더링 과정에서 생긴 임시 파일 삭제 및 SRT 저장
            try:
                if os.path.exists(temp_edited):
                    os.remove(temp_edited)
                
                # 사용자가 SRT 파일을 따로 쓸 수 있도록 최종 영상과 같은 이름으로 저장
                if os.path.exists(subtitle_srt):
                    import shutil
                    final_srt_path = os.path.splitext(output_video)[0] + ".srt"
                    shutil.move(subtitle_srt, final_srt_path)
            except Exception:
                pass
                    
            return {
                "final_result": output_video,
                "cut_points": cut_points
            }
        else:
            self._log("❌ 자막 병합 실패")
            return None

# =========================================================================
# 프론트엔드 연동용 통합 파이프라인 함수 (UI Worker에서 직접 호출)
# =========================================================================

def run_pipeline(video_path, settings, on_progress=None):
    """
    프론트엔드(AIWorker)에서 호출하는 통합 파이프라인.
    1. 오디오 추출
    2. 무음 구간 탐지(VAD)
    3. STT 및 불용어 탐지
    4. 데이터 병합 (자막, 무음, 불용어)하여 UI에서 요구하는 segments 리스트 반환
    """
    from extract_audio import extract_audio
    from export_json import detect_silence
    from transcriber import transcribe_video_to_srt
    import os
    
    if on_progress: on_progress(10)

    # 1. 오디오 추출
    os.makedirs(_DATA_DIR, exist_ok=True)
    temp_audio = os.path.join(_DATA_DIR, "temp_audio.wav")
    extract_audio(video_path, temp_audio)

    if on_progress: on_progress(30)

    # 2. VAD 분석 (무음 구간 탐지)
    silence_return_list, vad_results = detect_silence(temp_audio)
    silence_segments = vad_results.get("silence_segments", []) if vad_results else []
    duration = vad_results.get("video_info", {}).get("total_duration", 0.0) if vad_results else 0.0

    if on_progress: on_progress(60)

    # 3. STT 및 불용어 탐지
    srt_out = os.path.join(_DATA_DIR, "subtitle.srt")
    _models = ["tiny", "base", "small", "medium", "large"]
    model_size = "small"
    if isinstance(settings, dict):
        model_val = settings.get("whisper_model", 2)
        if isinstance(model_val, int) and 0 <= model_val < len(_models):
            model_size = _models[model_val]
        elif isinstance(model_val, str) and model_val in _models:
            model_size = model_val
            
    _, _, stt_result, ai_result = transcribe_video_to_srt(video_path, srt_out, model_size=model_size)
    
    if on_progress: on_progress(80)
    
    # 4. 데이터 병합
    stt_segments = stt_result.get("segments", []) if stt_result else []
    stopword_segments = ai_result.get("cut_points", []) if ai_result else []
    
    # 중복 제거된 모든 시간 경계점 수집
    boundaries = set([0.0, duration])
    for s in stt_segments:
        boundaries.add(s['start'])
        boundaries.add(s['end'])
    for s in silence_segments:
        boundaries.add(s['start'])
        boundaries.add(s['end'])
    for s in stopword_segments:
        boundaries.add(s['start'])
        boundaries.add(s['end'])
        
    boundaries = sorted(list(boundaries))
    merged = []
    
    for i in range(len(boundaries)-1):
        start = boundaries[i]
        end = boundaries[i+1]
        mid = (start + end) / 2.0
        
        if end - start < 0.01:
            continue
            
        # 속성 확인 (중간 지점이 포함되는지)
        is_silence = any(s['start'] <= mid <= s['end'] for s in silence_segments)
        is_stopword = any(s['start'] <= mid <= s['end'] for s in stopword_segments)
        subtitle = next((s for s in stt_segments if s['start'] <= mid <= s['end']), None)
        
        # UI는 ms 단위로 데이터를 요구하므로 변환
        start_ms = int(start * 1000)
        end_ms = int(end * 1000)
        
        if is_silence:
            merged.append({"start": start_ms, "end": end_ms, "text": "", "keep": False, "reason": "무음"})
        elif is_stopword:
            merged.append({"start": start_ms, "end": end_ms, "text": "(불용어)", "keep": False, "reason": "불용어"})
        elif subtitle:
            merged.append({"start": start_ms, "end": end_ms, "text": subtitle['text'], "keep": True, "reason": "정상"})
        else:
            merged.append({"start": start_ms, "end": end_ms, "text": "", "keep": True, "reason": "정상"})
            
    if on_progress: on_progress(100)
    return merged

def render_pipeline(input_video, segments, output_video=None):
    """
    사용자가 프론트엔드에서 수정한 segments 데이터를 바탕으로 컷편집 및 자막 생성
    """
    from editor import create_final_edited_video, add_subtitles_to_video
    from transcriber import format_time
    import os

    if output_video is None:
        output_video = os.path.join(_DATA_DIR, "final_output.mp4")
    
    # 1. 편집할 구간(잘라낼 구간) 계산 (ms -> 초 변환)
    silence_segments = []
    for seg in segments:
        if not seg.get("keep", True):
            silence_segments.append({
                "start": seg["start"] / 1000.0,
                "end": seg["end"] / 1000.0
            })
            
    # 2. 유지되는 구간만 모아서 연속된 타임라인으로 새로운 SRT 자막 생성
    os.makedirs(_DATA_DIR, exist_ok=True)
    temp_srt = os.path.join(_DATA_DIR, "temp_subtitle.srt")
    with open(temp_srt, "w", encoding="utf-8") as f:
        new_current_time = 0.0
        subtitle_index = 1
        for seg in segments:
            if seg.get("keep", True):
                duration = (seg["end"] - seg["start"]) / 1000.0
                text = seg.get("text", "").strip()
                if text and text != "(불용어)":
                    start_str = format_time(new_current_time)
                    end_str = format_time(new_current_time + duration)
                    f.write(f"{subtitle_index}\n{start_str} --> {end_str}\n{text}\n\n")
                    subtitle_index += 1
                new_current_time += duration

    # 3. 비디오 컷편집 수행
    temp_edited = os.path.join(_DATA_DIR, "temp_edited.mp4")
    create_final_edited_video(input_video, silence_segments, temp_edited)
    
    # 4. 최종 영상에 새로 만든 자막 병합
    if os.path.exists(temp_edited):
        add_subtitles_to_video(temp_edited, temp_srt, output_video, language='ko')
        # 용량 절약을 위해 임시 컷편집본 삭제
        os.remove(temp_edited)
        
    return output_video