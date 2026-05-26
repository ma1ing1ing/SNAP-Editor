import os
from typing import Optional
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QTableWidgetItem, QPushButton, QVBoxLayout, QMessageBox
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.uic import loadUi
from PyQt6.QtCore import QSettings

from settings_dialog import SettingsDialog
from analysis_popup import AnalysisPopup
from video_player import VideoPlayer
from workers.ai_worker import AIWorker
from workers.render_worker import RenderWorker
from workers.stt_worker import STTWorker
from utils.time_formatter import format_time
from widgets.waveform_widget import WaveformWidget


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_window.ui")
        loadUi(ui_path, self)

        self._video_path = None
        self._ai_worker = None
        self._stt_worker = None
        self._render_worker = None
        self._segments: list = []
        self._analysis_popup: Optional[AnalysisPopup] = None

        self._video_player = VideoPlayer(self.video_frame)
        self._waveform = self._setup_waveform()

        self._connect_signals()

    def _setup_waveform(self) -> WaveformWidget:
        waveform = WaveformWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(waveform)
        self.timeline_frame.setLayout(layout)
        return waveform

    def _connect_signals(self):
        # 파일
        self.btn_open_file.clicked.connect(self._open_file)

        # 재생 컨트롤
        self.btn_play.clicked.connect(self._video_player.play)
        self.btn_pause.clicked.connect(self._video_player.pause)

        # 슬라이더 드래그
        self.slider_timeline.sliderPressed.connect(lambda: self._video_player.set_seeking(True))
        self.slider_timeline.sliderReleased.connect(self._on_slider_released)

        # VideoPlayer → 슬라이더 + label_time + waveform playhead
        self._video_player.position_changed.connect(self._on_position_changed)

        # 구간 목록 선택 → waveform 하이라이트 + 자막 표시
        self.list_segments.currentCellChanged.connect(self._on_segment_selected)

        # 자막 수정 확인
        self.btn_subtitle_confirm.clicked.connect(self._on_subtitle_confirm)

        # AI
        self.btn_start_process.clicked.connect(self._start_analysis)

        # 렌더링
        self.btn_render.clicked.connect(self._start_render)

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
        self.btn_render.setEnabled(False)
        self._video_player.load(path)

        self._open_settings()

    # ── 재생 컨트롤 ───────────────────────────────────────────────────────────

    def _on_slider_released(self):
        self._video_player.seek(self.slider_timeline.value())
        self._video_player.set_seeking(False)

    def _on_position_changed(self, position: int, duration: int):
        self.slider_timeline.setMaximum(duration)
        self.slider_timeline.setValue(position)
        self.label_time.setText(f"{format_time(position)} / {format_time(duration)}")
        self._waveform.set_position(position)

    # ── AI 분석 ───────────────────────────────────────────────────────────────

    def _start_analysis(self):
        if not self._video_path:
            self.label_status.setText("⚠ 파일을 먼저 선택해주세요")
            return

        if self._ai_worker and self._ai_worker.isRunning():
            return

        # 팝업 생성 (안 C)
        self._analysis_popup = AnalysisPopup(parent=self)
        self._analysis_popup.setModal(True)

        settings = self._load_settings()
        self._ai_worker = AIWorker(self._video_path, settings)

        # 팝업 ↔ 워커 시그널 연결
        self._ai_worker.progress_updated.connect(self._analysis_popup.update_progress)
        self._ai_worker.progress_updated.connect(self.progress_bar.setValue)
        self._ai_worker.status_changed.connect(self._analysis_popup.update_status)
        self._ai_worker.status_changed.connect(self.label_status.setText)
        self._ai_worker.waveform_ready.connect(self._waveform.set_waveform)
        self._ai_worker.analysis_complete.connect(self._on_analysis_complete)
        self._ai_worker.error_occurred.connect(self._on_analysis_error)

        # 취소 버튼 → 워커 중단
        self._analysis_popup.rejected.connect(self._ai_worker.terminate)

        self._ai_worker.start()
        self.label_status.setText("AI 분석 중...")
        self._analysis_popup.open()

    def _on_analysis_complete(self, segments: list):
        self._populate_segments(segments)

        count = len(segments)
        if self._analysis_popup:
            self._analysis_popup.mark_step1_complete(count)

        self.label_status.setText(f"✅ {count}개 구간 감지됨 — 자막 생성 중...")

        self._stt_worker = STTWorker(self._video_path, self._segments, self._load_settings())
        self._stt_worker.progress_updated.connect(self.progress_bar.setValue)
        if self._analysis_popup:
            self._stt_worker.progress_updated.connect(self._analysis_popup.update_progress)
        self._stt_worker.status_changed.connect(self.label_status.setText)
        if self._analysis_popup:
            self._stt_worker.status_changed.connect(self._analysis_popup.update_status)
        self._stt_worker.stt_complete.connect(self._on_stt_complete)
        self._stt_worker.error_occurred.connect(self._on_stt_error)
        
        # 취소 버튼 → STT 워커 중단 연결
        if self._analysis_popup:
            self._analysis_popup.rejected.connect(self._stt_worker.terminate)
            
        self._stt_worker.start()

    def _on_stt_complete(self, updated_segments: list):
        self._populate_segments(updated_segments)
        self.btn_render.setEnabled(True)
        self.label_status.setText(
            "✅ 자막 생성 완료 — 오른쪽 목록에서 O / X로 구간을 승인 후 렌더링하세요"
        )
        if self._analysis_popup:
            self._analysis_popup.mark_complete(len(self._segments))

    def _on_stt_error(self, message: str):
        self.label_status.setText("⚠ 자막 생성 실패 — 구간 목록은 유지됩니다")
        if self._analysis_popup:
            self._analysis_popup.mark_complete(len(self._segments))

    def _on_analysis_error(self, message: str):
        if self._analysis_popup:
            self._analysis_popup.reject()
        self.label_status.setText("⚠ 분석 실패 — 다시 시도해주세요")
        QMessageBox.critical(self, "분석 오류", f"{message}\n\n다시 시도해주세요.")

    # ── 렌더링 ────────────────────────────────────────────────────────────────

    def _start_render(self):
        if not self._video_path or not self._segments:
            self.label_status.setText("⚠ 분석 완료 후 렌더링할 수 있습니다")
            return

        if self._render_worker and self._render_worker.isRunning():
            return

        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "렌더링 결과 저장",
            os.path.splitext(self._video_path)[0] + "_edited.mp4",
            "Videos (*.mp4)",
        )
        if not output_path:
            return

        self.btn_render.setEnabled(False)
        self.btn_open_file.setEnabled(False)
        self.btn_start_process.setEnabled(False)
        self.btn_settings.setEnabled(False)
        self._render_worker = RenderWorker(self._video_path, self._segments, self._load_settings(), output_path)
        self._render_worker.progress_updated.connect(self.progress_bar.setValue)
        self._render_worker.status_changed.connect(self.label_status.setText)
        self._render_worker.render_complete.connect(self._on_render_complete)
        self._render_worker.error_occurred.connect(self._on_render_error)
        self._render_worker.start()
        self.label_status.setText("렌더링 시작...")

    def _on_render_complete(self, output_path: str, updated_segments: list):
        self._segments = updated_segments
        self._refresh_segment_text()
        self.btn_render.setEnabled(True)
        self.btn_open_file.setEnabled(True)
        self.btn_start_process.setEnabled(True)
        self.btn_settings.setEnabled(True)

        # 결과 영상 플레이어에 로드 (원본 경로는 재렌더를 위해 유지)
        self.label_file_path.setText(output_path)
        self._video_player.load(output_path)

        self.label_status.setText("✅ 렌더링 완료 — 결과 영상을 재생해보세요")

        original_ms = max((s.get("end", 0) for s in self._segments), default=0)
        edited_ms   = sum(s["end"] - s["start"] for s in self._segments if s.get("keep", True))
        cut_ms      = original_ms - edited_ms

        def _fmt(ms: int) -> str:
            s = ms // 1000
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

        QMessageBox.information(
            self,
            "렌더링 완료",
            f"저장 경로\n{output_path}\n\n"
            f"원본 길이   {_fmt(original_ms)}\n"
            f"편집 길이   {_fmt(edited_ms)}\n"
            f"단축된 시간  {_fmt(cut_ms)}",
        )

    def _on_render_error(self, message: str):
        self.btn_render.setEnabled(True)
        self.btn_open_file.setEnabled(True)
        self.btn_start_process.setEnabled(True)
        self.btn_settings.setEnabled(True)
        self.label_status.setText("⚠ 렌더링 실패 — 다시 시도해주세요")
        QMessageBox.critical(self, "렌더링 오류", f"{message}\n\n다시 시도해주세요.")

    def _refresh_segment_text(self):
        """렌더링 완료 후 STT 텍스트, 행 색상, 파형 구간을 일괄 갱신."""
        for row, seg in enumerate(self._segments):
            item = self.list_segments.item(row, 3)
            if item is not None:
                item.setText(seg.get("text", ""))
            self._apply_row_color(row)
            self._waveform.update_keep(row, seg.get("keep", True))

    def _populate_segments(self, segments: list):
        self._segments = [dict(seg, keep=seg.get("keep", True)) for seg in segments]

        tbl = self.list_segments
        tbl.setRowCount(0)
        tbl.setColumnCount(4)
        tbl.setHorizontalHeaderLabels(["시간", "✓", "✗", "자막"])
        tbl.setColumnWidth(0, 140)
        tbl.setColumnWidth(1, 35)
        tbl.setColumnWidth(2, 35)
        tbl.horizontalHeader().setStretchLastSection(True)

        for row, seg in enumerate(self._segments):
            tbl.insertRow(row)

            time_item = QTableWidgetItem(
                f"{format_time(seg.get('start', 0))} ~ {format_time(seg.get('end', 0))}"
            )
            tbl.setItem(row, 0, time_item)

            btn_ok = QPushButton("✓")
            btn_ok.setStyleSheet("color: #2e7d32; font-weight: bold;")
            btn_ok.clicked.connect(lambda _, r=row: self._set_keep(r, True))
            tbl.setCellWidget(row, 1, btn_ok)

            btn_x = QPushButton("✗")
            btn_x.setStyleSheet("color: #c62828; font-weight: bold;")
            btn_x.clicked.connect(lambda _, r=row: self._set_keep(r, False))
            tbl.setCellWidget(row, 2, btn_x)

            text_item = QTableWidgetItem(seg.get("text", ""))
            tbl.setItem(row, 3, text_item)

            self._apply_row_color(row)

        # waveform에 전체 구간 + 총 길이 전달
        duration_ms = max((s.get("end", 0) for s in self._segments), default=0)
        self._waveform.set_segments(self._segments, duration_ms)

    def _set_keep(self, row: int, keep: bool):
        self._segments[row]["keep"] = keep
        self._apply_row_color(row)
        self._waveform.update_keep(row, keep)

    def _apply_row_color(self, row: int):
        keep = self._segments[row].get("keep", True)
        color = QColor("#C8E6C9") if keep else QColor("#FFCDD2")
        item = self.list_segments.item(row, 0)
        if item:
            item.setBackground(color)

    # ── 설정 ──────────────────────────────────────────────────────────────────

    def _open_settings(self):
        dialog = SettingsDialog(parent=self)
        dialog.accepted.connect(self._highlight_words)
        dialog.accepted.connect(self._on_settings_saved)
        dialog.rejected.connect(self._on_settings_cancelled)
        dialog.exec()

    def _on_settings_cancelled(self):
        if self._video_path:
            self.label_status.setText("파일 로드 완료 — AI 분석 시작 버튼을 눌러주세요")

    def _on_settings_saved(self):
        s = QSettings("SNAP", "Editor")
        threshold = s.value("silence_threshold", 0.5)
        model_idx = int(s.value("whisper_model", 3))
        models = ["tiny", "base", "small", "medium", "large"]
        model_name = models[model_idx] if model_idx < len(models) else "medium"
        self.label_status.setText(
            f"✅ 설정 저장됨 (무음 기준: {threshold}초 / Whisper: {model_name})"
            + (" — AI 분석 시작 버튼을 눌러주세요" if self._video_path else "")
        )

    # ── 구간 선택 + 자막 ──────────────────────────────────────────────────────

    def _on_segment_selected(self, row: int, *_):
        self._waveform.set_selected(row)
        if row < 0 or row >= len(self._segments):
            return
        seg = self._segments[row]
        self._video_player.seek(seg.get('start', 0))
        text = seg.get("text", "")
        self.text_subtitle_edit.setPlainText(text)
        self.text_subtitle_edit.setEnabled(True)
        self.btn_subtitle_confirm.setEnabled(True)
        self._highlight_words()

    def _on_subtitle_confirm(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.inputMethod().commit()
        row = self.list_segments.currentRow()
        if 0 <= row < len(self._segments):
            new_text = self.text_subtitle_edit.toPlainText()
            self._segments[row]["text"] = new_text
            item = self.list_segments.item(row, 3)
            if item is not None:
                item.setText(new_text)

    def _highlight_words(self):
        words = self._load_highlight_words()
        doc = self.text_subtitle_edit.document()

        # 전체 서식 초기화
        clear_fmt = QTextCharFormat()
        cursor = QTextCursor(doc)
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.setCharFormat(clear_fmt)

        if not words:
            return

        highlight_fmt = QTextCharFormat()
        highlight_fmt.setBackground(QColor("#FFD700"))
        highlight_fmt.setForeground(QColor("#1a1a1a"))

        for word in words:
            cursor = doc.find(word)
            while not cursor.isNull():
                cursor.setCharFormat(highlight_fmt)
                cursor = doc.find(word, cursor)

    def _load_highlight_words(self):
        raw = QSettings("SNAP", "Editor").value("highlight_words", "")
        return [w.strip() for w in raw.split(",") if w.strip()]

    def _load_settings(self) -> dict:
        s = QSettings("SNAP", "Editor")
        return {
            "silence_threshold": float(s.value("silence_threshold", 0.3)),
            "whisper_model": int(s.value("whisper_model", 3)),
            "stopword_mode": s.value("stopword_mode", "default")
        }
