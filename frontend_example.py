import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                             QWidget, QTextBrowser, QProgressBar, QLabel)
from PyQt6.QtCore import QThread, pyqtSignal

from backend.backend_controller import BackendController

class BackendWorker(QThread):
    """
    QThread를 상속받아 백엔드 로직을 비동기적으로 실행하는 워커(Worker) 클래스입니다.
    UI 멈춤(Freezing) 현상을 방지합니다.
    """
    # 프론트엔드로 보낼 시그널 정의
    progress_updated = pyqtSignal(int)
    log_updated = pyqtSignal(str)
    step_finished = pyqtSignal(int, object) # step_number, result_data

    def __init__(self, step, kwargs):
        super().__init__()
        self.step = step
        self.kwargs = kwargs
        
        # 백엔드 컨트롤러에 콜백을 바인딩 (QThread 안에서 동작)
        self.controller = BackendController(
            progress_callback=self.emit_progress,
            log_callback=self.emit_log
        )

    def emit_progress(self, value):
        self.progress_updated.emit(value)

    def emit_log(self, message):
        self.log_updated.emit(message)

    def run(self):
        """스레드가 시작되면 호출되는 메인 메서드입니다."""
        try:
            if self.step == 1:
                result = self.controller.run_step1_extract_and_vad(**self.kwargs)
                self.step_finished.emit(1, result)
            elif self.step == 3:
                result = self.controller.run_step3_render_video(**self.kwargs)
                self.step_finished.emit(3, result)
            elif self.step == 4:
                result = self.controller.run_step4_stt_and_subtitle(**self.kwargs)
                self.step_finished.emit(4, result)
        except Exception as e:
            self.emit_log(f"❌ Error during step {self.step}: {str(e)}")
            self.step_finished.emit(self.step, None)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SNAP-Editor Pipeline Qt Example")
        self.resize(600, 450)

        # UI 요소 구성
        layout = QVBoxLayout()
        
        self.status_label = QLabel("상태: 대기 중")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.log_browser = QTextBrowser()
        layout.addWidget(self.log_browser)

        self.btn_step1 = QPushButton("Step 1: 오디오 추출 & VAD & JSON 생성")
        self.btn_step1.clicked.connect(self.run_step1)
        layout.addWidget(self.btn_step1)

        self.btn_step2 = QPushButton("Step 2: 뷰어로 결과 확인 및 수정 (프론트엔드)")
        self.btn_step2.clicked.connect(self.run_step2)
        layout.addWidget(self.btn_step2)

        self.btn_step3 = QPushButton("Step 3: JSON 기반 컷편집 렌더링")
        self.btn_step3.clicked.connect(self.run_step3)
        layout.addWidget(self.btn_step3)

        self.btn_step4 = QPushButton("Step 4: STT 및 자막 파일 생성")
        self.btn_step4.clicked.connect(self.run_step4)
        layout.addWidget(self.btn_step4)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # ----------------------------------------------------
        # 작업에 필요한 상태(State) 파일 경로들
        # ----------------------------------------------------
        # 예제 실행을 위해 backend/Data 디렉토리 하위의 파일로 가정합니다.
        self.input_video = os.path.abspath("./backend/Data/문재인_대통령_퇴임연설.MP4") # 테스트용 입력 비디오 이름 (수정 필요)
        self.temp_audio = os.path.abspath("./backend/Data/temp_audio.wav")
        self.output_json = os.path.abspath("./backend/Data/cut_analysis.json")
        self.edited_video = os.path.abspath("./backend/Data/edited_video.mp4")
        self.subtitle_srt = os.path.abspath("./backend/Data/subtitle.srt")
        self.final_result = os.path.abspath("./backend/Data/final_result.mp4")

    def append_log(self, msg):
        """로그 텍스트 브라우저에 텍스트 추가"""
        self.log_browser.append(msg)

    def update_progress(self, val):
        """프로그레스 바 업데이트"""
        self.progress_bar.setValue(val)

    def handle_step_finished(self, step, result):
        """QThread 작업이 끝났을 때 호출되는 슬롯"""
        self.status_label.setText(f"상태: Step {step} 완료")
        if result:
            self.append_log(f"✅ Step {step} 성공: {result}")
        else:
            self.append_log(f"❌ Step {step} 실패")
        
        # 모든 버튼 다시 활성화
        self.set_buttons_enabled(True)

    def set_buttons_enabled(self, enabled):
        self.btn_step1.setEnabled(enabled)
        self.btn_step2.setEnabled(enabled)
        self.btn_step3.setEnabled(enabled)
        self.btn_step4.setEnabled(enabled)

    def run_backend_step(self, step, kwargs):
        """공통 백엔드 실행 메서드"""
        self.status_label.setText(f"상태: Step {step} 진행 중...")
        self.progress_bar.setValue(0)
        self.set_buttons_enabled(False) # 실행 중 중복 클릭 방지

        # 비동기 QThread 생성 및 실행
        self.worker = BackendWorker(step, kwargs)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.log_updated.connect(self.append_log)
        self.worker.step_finished.connect(self.handle_step_finished)
        self.worker.start()

    # ==========================
    # 각 스텝 버튼의 Click 이벤트
    # ==========================
    def run_step1(self):
        kwargs = {
            "input_video": self.input_video,
            "temp_audio": self.temp_audio,
            "output_json": self.output_json
        }
        self.run_backend_step(1, kwargs)

    def run_step2(self):
        self.append_log("▶ [Step 2] 뷰어 실행 (파형 및 무음 구간 시각화)")
        self.status_label.setText("상태: Step 2 진행 중 (뷰어 창 대기 중...)")
        self.set_buttons_enabled(False)
        
        # matplotlib 창을 띄워야 하므로 GUI 스레드 안전성을 위해 메인 스레드에서 직접 실행합니다.
        try:
            # 임시 컨트롤러 객체 생성하여 호출
            controller = BackendController(log_callback=self.append_log)
            result = controller.run_step2_view_waveform(self.temp_audio, self.output_json)
            
            if result:
                self.handle_step_finished(2, result)
            else:
                self.handle_step_finished(2, None)
        except Exception as e:
            self.append_log(f"❌ Step 2 뷰어 실행 중 오류 발생: {str(e)}")
            self.handle_step_finished(2, None)

    def run_step3(self):
        kwargs = {
            "input_video": self.input_video,
            "json_path": self.output_json,
            "edited_video": self.edited_video
        }
        self.run_backend_step(3, kwargs)

    def run_step4(self):
        kwargs = {
            "edited_video": self.edited_video,
            "subtitle_srt": self.subtitle_srt,
            "final_result": self.final_result
        }
        self.run_backend_step(4, kwargs)


if __name__ == "__main__":
    app = QApplication(sys.path)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
