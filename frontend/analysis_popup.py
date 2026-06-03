import time
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QTimer
from PyQt6.uic import loadUi
from utils.resource_path import resource_path


class AnalysisPopup(QDialog):
    """
    AI 분석 중 → 완료 팝업.
    - 분석 중: 프로그레스 바 + 경과/예상 시간
    - 완료 시: mark_complete() 호출 → 요약 화면으로 전환
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        loadUi(resource_path("analysis_popup.ui"), self)

        self._start_time = time.time()
        self._cancelled = False

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick_elapsed)
        self._timer.start(1000)

        self.setWindowTitle("AI 분석 중")
        self.label_title.setWordWrap(True)
        self.label_title.setText("AI 분석 중입니다...")
        self.btn_cancel.setText("취소")
        self.btn_cancel.clicked.connect(self._on_cancel)

    # ── 분석 중 업데이트 ──────────────────────────────────────────────────────

    def update_progress(self, value: int):
        self.progress_bar.setValue(value)
        if value > 5:
            elapsed = time.time() - self._start_time
            estimated_total = elapsed / (value / 100)
            remaining = max(0, int(estimated_total - elapsed))
            m, s = divmod(remaining, 60)
            self.label_remaining.setText(f"{m:02d}:{s:02d}")

    def update_status(self, text: str):
        self.label_title.setText(text)

    def _tick_elapsed(self):
        elapsed = int(time.time() - self._start_time)
        m, s = divmod(elapsed, 60)
        self.label_elapsed.setText(f"{m:02d}:{s:02d}")

    # ── 완료 전환 ─────────────────────────────────────────────────────────────

    def mark_step1_complete(self, segment_count: int):
        """VAD 완료 — 자막 생성 단계로 전환."""
        self._timer.stop()
        self._timer.timeout.disconnect(self._tick_elapsed)
        self._step1_time = int(time.time() - self._start_time)

        self.setWindowTitle("자막 생성 중")
        self.label_title.setText("1. 구간 분류 완료  →  2. 자막 생성 중...")
        self.progress_bar.setValue(50)

        self.label_elapsed_title.setText("감지된 구간")
        self.label_elapsed.setText(f"{segment_count}개")
        self.label_remaining_title.setText("현재 단계")
        self.label_remaining.setText("자막 생성 중...")

        self._stt_start_time = time.time()
        self._timer.timeout.connect(self._tick_stt_elapsed)
        self._timer.start(1000)

    def _tick_stt_elapsed(self):
        elapsed = int(time.time() - self._stt_start_time)
        m, s = divmod(elapsed, 60)
        self.label_remaining.setText(f"자막 생성 중... {m:02d}:{s:02d}")

    def mark_complete(self, segment_count: int):
        self._timer.stop()
        self.setWindowTitle("분석 완료")
        self.label_title.setText("분석 및 자막 생성이 완료되었습니다")
        self.progress_bar.setValue(100)

        self.label_elapsed_title.setText("감지된 구간")
        self.label_elapsed.setText(f"{segment_count}개")
        self.label_remaining_title.setText("다음 단계")
        self.label_remaining.setText("O / X로 구간을 승인해주세요")

        self.btn_cancel.setText("확인")
        self.btn_cancel.clicked.disconnect()
        self.btn_cancel.clicked.connect(self.accept)

    # ── 취소 ──────────────────────────────────────────────────────────────────

    def _on_cancel(self):
        self._cancelled = True
        self._timer.stop()
        self.reject()

    def was_cancelled(self) -> bool:
        return self._cancelled
