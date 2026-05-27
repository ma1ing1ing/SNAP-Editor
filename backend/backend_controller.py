import os
import json
import sys

# 현재 모듈(backend)을 경로에 추가하여 모듈 내 함수들을 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# backend/Data 경로 — 실행 위치에 관계없이 이 파일 기준으로 고정
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Data")

from backend.extract_audio import extract_audio
from backend.editor import create_final_edited_video, add_subtitles_to_video
from transcriber import transcribe_video_to_srt
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

    # 🚀 [수정 포인트 2] 프론트엔드가 호출하는 파라미터 이름(threshold)으로 완벽하게 맞춤!
    def run_step1_extract_and_vad(self, input_video, temp_audio, output_json,
                                  threshold=0.3, min_silence_ms=500, min_speech_ms=250):
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
        
        # 2. VAD 분석 (무음 구간 탐지) 및 상세 데이터 추출
        self._log("AI 기반 VAD 무음 구간 분석 및 상세 데이터 추출 중...")
        
        # 명세서에 맞게 무음 튜플 리스트(silence_list)와 상세 JSON 데이터(detailed_json_data)를 통째로 받아옴
        silence_list, detailed_json_data = detect_silence(temp_audio)
        
        self._progress(80)
        
        # 3. 분석 결과를 JSON 파일로 저장
        self._log("상세 분석 결과 JSON 저장 중...")
        
        # 만약 detailed_json_data가 이미 문자열이라면 그대로 쓰고, 딕셔너리면 dump로 저장하는 안전장치
        with open(output_json, 'w', encoding='utf-8') as f:
            if isinstance(detailed_json_data, str):
                f.write(detailed_json_data)
            else:
                json.dump(detailed_json_data, f, indent=4, ensure_ascii=False)
            
        self._progress(100)
        self._log(f"✅ [Step 1] 완료. 상세 JSON 파일 저장됨: {output_json}")
        
        # 🚀 [수정 포인트 3 - 멘토의 무적 방어 코드] 
        # 튜플 (0.0, 0.32)를 프론트엔드가 정확히 원하는 {"start": 0.0, "end": 0.32} 형태로 강제 변환!
        formatted_segments = [{"start": s, "end": e} for s, e in silence_list]
        
        # 다음 단계로 넘길 상태(State) 데이터 리턴
        return {
            "temp_audio": temp_audio,
            "json_path": output_json,
            "silence_list": formatted_segments 
        }
    
    def run_step2_stt(self, video_path, srt_path, whisper_model, stopword_mode="default"):
        """
        Step 2: STTWorker에서 호출하는 통합 STT 메서드
        """
        self._log(f"▶ STT 모델({whisper_model}) 로드 중...")
        self._progress(0)
        
        from transcriber import transcribe_video_to_srt
        
        # transcriber를 호출하며 status_callback을 전달
        srt_path, detected_lang, stt_result, ai_result = transcribe_video_to_srt(
            video_path, srt_path, model_size=whisper_model,
            status_callback=self._log, progress_callback=self._progress,
            stopword_mode=stopword_mode
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
            # 자막 싱크가 약간 빠르게 나오는 현상을 방지하기 위해 0.15초(150ms) 지연 보정 적용
            delay_offset = 0.15
            for seg in segments:
                if seg.get("keep", True):
                    duration = (seg["end"] - seg["start"]) / 1000.0
                    text = seg.get("text", "").strip()
                    if text and text != "(불용어)":
                        start_str = format_time(new_current_time + delay_offset)
                        end_str = format_time(new_current_time + duration + delay_offset)
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

