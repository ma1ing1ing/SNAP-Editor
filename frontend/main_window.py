import os
from PyQt6.QtWidgets import QMainWindow, QFileDialog
from PyQt6.uic import loadUi
from PyQt6.QtCore import QSettings

from settings_dialog import SettingsDialog
from PyQt6.QtWidgets import QTableWidgetItem
from video_player import VideoPlayer
from workers.ai_worker import AIWorker
from utils.time_formatter import format_time


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_window.ui")
        loadUi(ui_path, self)

        self._video_path = None
        self._ai_worker = None

        self._video_player = VideoPlayer(self.video_frame)

        self._connect_signals()

    def _connect_signals(self):
        # 파일
        self.btn_open_file.clicked.connect(self._open_file)

        # 재생 컨트롤
        self.btn_play.clicked.connect(self._video_player.play)
        self.btn_pause.clicked.connect(self._video_player.pause)

        # 슬라이더 드래그
        self.slider_timeline.sliderPressed.connect(lambda: self._video_player.set_seeking(True))
        self.slider_timeline.sliderReleased.connect(self._on_slider_released)

        # VideoPlayer → 슬라이더 + label_time
        self._video_player.position_changed.connect(self._on_position_changed)

        # AI
        self.btn_start_process.clicked.connect(self._start_analysis)

        # 설정
        self.btn_settings.clicked.connect(self._open_settings)

    # ── 파일 열기 ──────────────────────────────────────────────────────────────

    def _open_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "영상 파일 선택",
            "",
            "Videos (*.mp4 *.mov *.avi *.mkv)",
        )
        if not path:
            return

        self._video_path = path
        self.label_file_path.setText(path)
        self.label_status.setText("파일 로드 완료")
        self.btn_render.setEnabled(True)
        self._video_player.load(path)

    # ── 재생 컨트롤 ───────────────────────────────────────────────────────────

    def _on_slider_released(self):
        self._video_player.seek(self.slider_timeline.value())
        self._video_player.set_seeking(False)

    def _on_position_changed(self, position: int, duration: int):
        self.slider_timeline.setMaximum(duration)
        self.slider_timeline.setValue(position)
        self.label_time.setText(f"{format_time(position)} / {format_time(duration)}")

    # ── AI 분석 ───────────────────────────────────────────────────────────────

    def _start_analysis(self):
        if not self._video_path:
            self.label_status.setText("파일을 먼저 선택해주세요")
            return

        if self._ai_worker and self._ai_worker.isRunning():
            return

        settings = self._load_settings()
        self._ai_worker = AIWorker(self._video_path, settings)
        self._ai_worker.progress_updated.connect(self.progress_bar.setValue)
        self._ai_worker.status_changed.connect(self.label_status.setText)
        self._ai_worker.analysis_complete.connect(self._on_analysis_complete)
        self._ai_worker.error_occurred.connect(self._on_analysis_error)
        self._ai_worker.start()

    def _on_analysis_complete(self, segments: list):
        self._populate_subtitles(segments)

    def _on_analysis_error(self, message: str):
        self.label_status.setText(f"오류: {message}")

    def _populate_subtitles(self, segments: list):
        self.list_subtitles.setRowCount(0)
        for row, seg in enumerate(segments):
            self.list_subtitles.insertRow(row)
            # seg = {"start": ms, "end": ms, "text": str, "keep": bool}
            self.list_subtitles.setItem(row, 0, QTableWidgetItem(
                f"{format_time(seg.get('start', 0))} ~ {format_time(seg.get('end', 0))}"
            ))
            self.list_subtitles.setItem(row, 1, QTableWidgetItem(seg.get("text", "")))

    # ── 설정 ──────────────────────────────────────────────────────────────────

    def _open_settings(self):
        dialog = SettingsDialog(parent=self)
        dialog.exec()
        self.label_status.setText("설정 저장 완료")

    def _load_settings(self) -> dict:
        s = QSettings("SNAP", "Editor")
        return {
            "silence_threshold": float(s.value("silence_threshold", 0.5)),
            "whisper_model": int(s.value("whisper_model", 3)),
        }
