import os
import json
import sys

# 현재 모듈(backend)을 경로에 추가하여 모듈 내 함수들을 임포트
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from extract_audio import extract_audio
from backend.editor import create_final_edited_video, add_subtitles_to_video
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
                                  vad_threshold=0.3, min_silence_ms=500, min_speech_ms=250):
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
        
        # 🚀 [수정 포인트 2] 팀원의 기존 함수 대신 멘티가 만든 함수 호출!
        # 명세서에 맞게 무음 튜플 리스트(silence_list)와 상세 JSON 데이터(detailed_json_data)를 통째로 받아옴
        silence_list, detailed_json_data = detect_silence(temp_audio)
        
        self._progress(80)
        
        # 3. 분석 결과를 JSON 파일로 저장
        self._log("상세 분석 결과 JSON 저장 중...")
        with open(output_json, 'w', encoding='utf-8') as f:
            # 🚀 [수정 포인트 3] 단순 리스트 대신 멘티가 만든 상세 구조(detailed_json_data) 저장!
            json.dump(detailed_json_data, f, indent=4, ensure_ascii=False)
            
        self._progress(100)
        self._log(f"✅ [Step 1] 완료. 상세 JSON 파일 저장됨: {output_json}")
        
        # 다음 단계로 넘길 상태(State) 데이터 리턴
        return {
            "temp_audio": temp_audio,
            "json_path": output_json,
            "silence_list": silence_list
        }
    
    def run_step2_get_waveform_data(self, temp_audio, num_points=3000):
        """
        프론트엔드에서 파형을 그리기 위한 데이터를 요청할 때 사용합니다.
        """
        self._log("▶ [Step 2] 시각화용 파형 데이터 추출 중...")
        self._progress(30)
        
        waveform_data = get_waveform_data(temp_audio, num_points=num_points)
        
        self._progress(100)
        self._log("✅ 파형 데이터 추출 완료. 프론트엔드로 전송합니다.")
        return waveform_data

    def run_step3_render_video(self, input_video, json_path, edited_video):
        """
        Step 3: 승인된 JSON 데이터를 바탕으로 컷편집 렌더링
        (Step 2는 프론트엔드에서 뷰어를 통해 유저 승인을 받는 단계이므로 백엔드에서는 분리됨)
        """
        self._log("▶ [Step 3] 컷편집 영상 렌더링 시작...")
        self._progress(0)
        
        if not os.path.exists(json_path):
            self._log(f"❌ JSON 파일을 찾을 수 없습니다: {json_path}")
            return None
            
        with open(json_path, 'r', encoding='utf-8') as f:
            silence_list = json.load(f)
            
        self._log(f"JSON 데이터 로드 완료 (무음 구간 {len(silence_list)}개). 렌더링 진행 중...")
        self._progress(20)
        
        # FFmpeg를 활용한 비디오 렌더링 시작 (editor.py 로직)
        create_final_edited_video(input_video, silence_list, edited_video)
        
        self._progress(100)
        self._log(f"✅ [Step 3] 완료. 편집된 영상 저장됨: {edited_video}")
        
        return {
            "edited_video": edited_video
        }
        
    def run_step4_stt_and_subtitle(self, edited_video, subtitle_srt, final_result,
                                   whisper_model_size='small'):
        """
        Step 4: 컷편집된 영상을 바탕으로 STT 및 자막 파일 생성
        """
        self._log("▶ [Step 4] STT 및 자막 생성 시작...")
        self._progress(0)
        
        self._log("Faster-Whisper & Kiwi 기반 STT 변환 진행 중... (시간이 소요될 수 있습니다)")
        self._progress(20)
        
        # STT 변환 및 자막 추출
        srt_path, detected_lang = transcribe_video_to_srt(
            edited_video, 
            subtitle_srt, 
            model_size=whisper_model_size
        )
        self._log(f"STT 완료. 자막 파일 생성됨: {srt_path} (감지된 언어: {detected_lang})")
        self._progress(70)
        
        # 컷편집된 영상에 자막을 메타데이터 트랙으로 병합
        self._log("자막을 영상에 병합 중...")
        success = add_subtitles_to_video(edited_video, srt_path, final_result, language=detected_lang)
        
        if success:
            self._progress(100)
            self._log(f"✅ [Step 4] 완료. 최종 영상(자막 포함) 생성됨: {final_result}")
            return {
                "final_result": final_result,
                "subtitle_srt": subtitle_srt,
                "language": detected_lang
            }
        else:
            self._log("❌ 자막 병합 실패")
            return None