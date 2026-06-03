import os
from typing import Optional
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QTableWidgetItem, QPushButton, QVBoxLayout, QMessageBox, QTimeEdit, QHBoxLayout, QLabel, QAbstractItemView, QStyle
from PyQt6.QtGui import QColor, QTextCharFormat, QTextCursor
from PyQt6.uic import loadUi
from PyQt6.QtCore import QSettings, QTime

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
        self._original_segments: list = []
        self._analysis_popup: Optional[AnalysisPopup] = None

        self._video_player = VideoPlayer(self.video_frame)
        self._waveform = self._setup_waveform()
        self._time_edit_start, self._time_edit_end = self._setup_time_editor()
        self._btn_merge = self._setup_merge_button()

        self._connect_signals()
        self._fix_layout()
        self._setup_title_bar()

    def _setup_time_editor(self):
        layout = self.frame_subtitle_editor.layout()

        header = QLabel("구간 시간")
        header.setStyleSheet("font-weight: bold; color: #555; font-size: 11px;")

        start_edit = QTimeEdit()
        start_edit.setDisplayFormat("mm:ss.zzz")
        start_edit.setEnabled(False)

        end_edit = QTimeEdit()
        end_edit.setDisplayFormat("mm:ss.zzz")
        end_edit.setEnabled(False)

        tilde = QLabel("~")
        tilde.setStyleSheet("color: #888;")

        start_edit.setFixedWidth(150)
        end_edit.setFixedWidth(150)

        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(start_edit)
        row.addWidget(tilde)
        row.addWidget(end_edit)
        row.addStretch()

        layout.insertWidget(1, header)
        layout.insertLayout(2, row)

        self.text_subtitle_edit.setMaximumHeight(90)

        return start_edit, end_edit

    def _setup_merge_button(self) -> QPushButton:
        small_btn_style = (
            "QPushButton {{ color: {fg}; font-size: 11px; border: 1px solid {fg}; border-radius: 3px; padding: 0 6px; }}"
            "QPushButton:disabled {{ color: #aaa; border-color: #ccc; }}"
        )

        btn_merge = QPushButton("구간 병합")
        btn_merge.setEnabled(False)
        btn_merge.setFixedHeight(22)
        btn_merge.setStyleSheet(small_btn_style.format(fg="#1c1c1e"))

        btn_reset = QPushButton("Reset")
        btn_reset.setEnabled(False)
        btn_reset.setFixedHeight(22)
        btn_reset.setStyleSheet(small_btn_style.format(fg="#1c1c1e"))

        from PyQt6.QtWidgets import QVBoxLayout, QFrame, QSizePolicy
        right_layout = self.findChild(QVBoxLayout, "layout_right")

        # ── 구간 목록: seg_container (헤더 + 리스트) ──
        seg_title = self.label_segment_title
        right_layout.removeWidget(seg_title)
        seg_title.setParent(None)
        right_layout.removeWidget(self.list_segments)

        seg_title.setStyleSheet("font-weight: bold; font-size: 12px;")
        seg_header_layout = QHBoxLayout()
        seg_header_layout.setContentsMargins(8, 5, 8, 5)
        seg_header_layout.addWidget(seg_title)
        seg_header_layout.addStretch()
        seg_header_layout.addWidget(btn_merge)

        header_frame = QFrame()
        header_frame.setObjectName("seg_header_frame")
        header_frame.setLayout(seg_header_layout)
        header_frame.setStyleSheet(
            "#seg_header_frame { background-color: #f5f5f7; border-bottom: 1px solid #d1d1d6;"
            " border-top-left-radius: 6px; border-top-right-radius: 6px; }"
        )

        self.list_segments.setFrameShape(QFrame.Shape.NoFrame)

        self._seg_container = QFrame()
        self._seg_container.setObjectName("seg_container")
        self._seg_container.setStyleSheet(
            "#seg_container { border: 1px solid #d1d1d6; border-radius: 6px; }"
        )
        self._seg_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container_layout.addWidget(header_frame)
        container_layout.addWidget(self.list_segments)
        self._seg_container.setLayout(container_layout)

        right_layout.insertWidget(0, self._seg_container)

        # ── 자막 편집: subtitle_container (헤더 + content) — seg_container와 동일한 구조 ──
        title_label = self.label_subtitle_editor_title
        title_label.setText("선택한 구간 편집")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        self.frame_subtitle_editor.layout().removeWidget(title_label)
        title_label.setParent(None)
        self.btn_subtitle_confirm.setParent(None)

        subtitle_header_layout = QHBoxLayout()
        subtitle_header_layout.setContentsMargins(8, 5, 8, 5)
        subtitle_header_layout.addWidget(title_label)
        subtitle_header_layout.addStretch()
        subtitle_header_layout.addWidget(btn_reset)
        subtitle_header_layout.addWidget(self.btn_subtitle_confirm)

        subtitle_header_frame = QFrame()
        subtitle_header_frame.setObjectName("subtitle_header_frame")
        subtitle_header_frame.setLayout(subtitle_header_layout)
        subtitle_header_frame.setStyleSheet(
            "#subtitle_header_frame { background-color: #f5f5f7; border-bottom: 1px solid #d1d1d6;"
            " border-top-left-radius: 6px; border-top-right-radius: 6px; }"
        )

        # frame_subtitle_editor를 content area로 재활용: 자체 스타일·크기 제약 제거
        right_layout.removeWidget(self.frame_subtitle_editor)
        self.frame_subtitle_editor.setFrameShape(QFrame.Shape.NoFrame)
        self.frame_subtitle_editor.setStyleSheet("")
        self.frame_subtitle_editor.setMinimumHeight(0)
        self.frame_subtitle_editor.setMaximumHeight(16777215)
        content_layout = self.frame_subtitle_editor.layout()
        content_layout.setContentsMargins(8, 6, 8, 6)
        content_layout.setSpacing(2)
        # btn_subtitle_confirm 제거 후 빈 채로 남은 layout_subtitle_edit_buttons 제거
        content_layout.removeItem(self.layout_subtitle_edit_buttons)
        # 남은 여백을 하단으로 밀기
        from PyQt6.QtWidgets import QSpacerItem, QSizePolicy as SP
        content_layout.addSpacerItem(QSpacerItem(0, 0, SP.Policy.Minimum, SP.Policy.Expanding))

        self._subtitle_container = QFrame()
        self._subtitle_container.setObjectName("subtitle_container")
        self._subtitle_container.setStyleSheet(
            "#subtitle_container { border: 1px solid #d1d1d6; border-radius: 6px; }"
        )
        self._subtitle_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        subtitle_outer_layout = QVBoxLayout()
        subtitle_outer_layout.setContentsMargins(0, 0, 0, 0)
        subtitle_outer_layout.setSpacing(0)
        subtitle_outer_layout.addWidget(subtitle_header_frame)
        subtitle_outer_layout.addWidget(self.frame_subtitle_editor)
        self._subtitle_container.setLayout(subtitle_outer_layout)

        right_layout.insertWidget(1, self._subtitle_container)

        self._btn_reset = btn_reset
        return btn_merge

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj in (self.video_frame, self._video_player.video_widget) and event.type() == QEvent.Type.Resize:
            self._apply_video_mask()
        return super().eventFilter(obj, event)

    def _apply_video_mask(self):
        from PyQt6.QtGui import QBitmap, QPainter
        from PyQt6.QtCore import Qt
        for widget in (self.video_frame, self._video_player.video_widget):
            bmp = QBitmap(widget.size())
            bmp.fill(Qt.GlobalColor.color0)
            p = QPainter(bmp)
            p.setBrush(Qt.GlobalColor.color1)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(widget.rect(), 10, 10)
            p.end()
            widget.setMask(bmp)

    def _setup_title_bar(self):
        from PyQt6.QtWidgets import QVBoxLayout, QFrame, QSizePolicy
        from PyQt6.QtGui import QPixmap, QFont
        from PyQt6.QtCore import Qt

        text_label = QLabel("SNAP")
        font = QFont()
        font.setPointSize(24)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 4)
        font.setBold(True)
        text_label.setFont(font)
        text_label.setStyleSheet("color: white;")

        center_layout = QHBoxLayout()
        center_layout.setSpacing(8)
        center_layout.addWidget(text_label)

        bar_layout = QHBoxLayout()
        bar_layout.addLayout(center_layout)
        bar_layout.addStretch()
        bar_layout.setContentsMargins(12, 4, 12, 4)

        bar = QFrame()
        bar.setStyleSheet("background-color: #1c1c1e; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        bar.setLayout(bar_layout)
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        main_layout = self.findChild(QVBoxLayout, "verticalLayout_main")
        main_layout.insertWidget(0, bar)

    def _fix_layout(self):
        from PyQt6.QtWidgets import QVBoxLayout

        # 우측 패널 비율: seg_container(1) : subtitle_container(fixed)
        right_layout = self.findChild(QVBoxLayout, "layout_right")
        seg_idx = right_layout.indexOf(self._seg_container)
        right_layout.setStretch(seg_idx, 1)

        # 파형 190px, 편집 패널 220px 고정
        self.timeline_frame.setFixedHeight(190)
        self._subtitle_container.setFixedHeight(220)

        # 바깥 여백: 좌12 상8 우12 하12
        main_layout = self.findChild(QVBoxLayout, "verticalLayout_main")
        main_layout.setContentsMargins(12, 8, 12, 12)

        # 영상/파형 박스 라운딩 제거
        self.video_frame.setStyleSheet("QFrame { border-radius: 0px; background-color: #000; }")
        self.timeline_frame.setStyleSheet("QFrame { border-radius: 0px; }")
        self.video_frame.installEventFilter(self)
        self._video_player.video_widget.installEventFilter(self)

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

        # 재생 컨트롤 (토글 버튼)
        self.btn_pause.hide()
        self.btn_play.setText("")
        self.btn_play.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_play.clicked.connect(self._video_player.toggle)
        self._video_player.playing_changed.connect(self._on_playing_changed)

        # ±5초 seek 버튼
        from PyQt6.QtWidgets import QHBoxLayout
        controls_layout = self.findChild(QHBoxLayout, "layout_controls")
        play_idx = controls_layout.indexOf(self.btn_play)

        btn_back = QPushButton()
        btn_back.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSeekBackward))
        btn_back.setFixedWidth(36)
        btn_back.clicked.connect(lambda: self._seek_relative(-5000))
        controls_layout.insertWidget(play_idx, btn_back)

        btn_forward = QPushButton()
        btn_forward.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaSeekForward))
        btn_forward.setFixedWidth(36)
        btn_forward.clicked.connect(lambda: self._seek_relative(5000))
        controls_layout.insertWidget(play_idx + 2, btn_forward)

        # 슬라이더 드래그
        self.slider_timeline.sliderPressed.connect(lambda: self._video_player.set_seeking(True))
        self.slider_timeline.sliderReleased.connect(self._on_slider_released)

        # VideoPlayer → 슬라이더 + label_time + waveform playhead
        self._video_player.position_changed.connect(self._on_position_changed)

        # 구간 목록 선택 → waveform 하이라이트 + 자막 표시
        self.list_segments.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_segments.currentCellChanged.connect(self._on_segment_selected)
        self.list_segments.itemSelectionChanged.connect(self._on_selection_changed)

        # 자막 수정 확인
        self.btn_subtitle_confirm.clicked.connect(self._on_subtitle_confirm)

        # 구간 병합 / Reset
        self._btn_merge.clicked.connect(self._merge_segments)
        self._btn_reset.clicked.connect(self._reset_segment)

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

    def _on_playing_changed(self, is_playing: bool):
        icon = QStyle.StandardPixmap.SP_MediaPause if is_playing else QStyle.StandardPixmap.SP_MediaPlay
        self.btn_play.setIcon(self.style().standardIcon(icon))

    def _seek_relative(self, delta_ms: int):
        current = self.slider_timeline.value()
        duration = self.slider_timeline.maximum()
        self._video_player.seek(max(0, min(current + delta_ms, duration)))

    def _on_slider_released(self):
        self._video_player.seek(self.slider_timeline.value())
        self._video_player.set_seeking(False)

    def _on_position_changed(self, position: int, duration: int):
        self.slider_timeline.setMaximum(duration)
        self.slider_timeline.setValue(position)
        self.label_time.setText(f"{format_time(position)} / {format_time(duration)}")
        self._waveform.set_position(position)
        
        # 재생 위치에 따라 구간 목록 동기화
        if not getattr(self, "_is_user_scrolling", False):  # 스크롤 중 방해 방지용 (선택)
            for i, seg in enumerate(self._segments):
                if seg.get("start", 0) <= position <= seg.get("end", 0):
                    if self.list_segments.currentRow() != i:
                        self._is_auto_selecting = True
                        self.list_segments.selectRow(i)
                        self._is_auto_selecting = False
                    break

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
        self._original_segments = [dict(seg) for seg in self._segments]
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

        btn_ok = self.list_segments.cellWidget(row, 1)
        btn_x  = self.list_segments.cellWidget(row, 2)
        if btn_ok:
            btn_ok.setStyleSheet(
                "color: #fff; background: #2e7d32; font-weight: bold; border-radius: 3px;"
                if keep else
                "color: #aaa; background: transparent; font-weight: normal;"
            )
        if btn_x:
            btn_x.setStyleSheet(
                "color: #fff; background: #c62828; font-weight: bold; border-radius: 3px;"
                if not keep else
                "color: #aaa; background: transparent; font-weight: normal;"
            )

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

    def _get_selected_rows(self) -> list[int]:
        return sorted({idx.row() for idx in self.list_segments.selectedIndexes()})

    def _on_selection_changed(self):
        rows = self._get_selected_rows()
        self._btn_merge.setEnabled(len(rows) >= 2)

    def _on_segment_selected(self, row: int, *_):
        self._waveform.set_selected(row)
        if row < 0 or row >= len(self._segments):
            return

        # 다중 선택 중이면 편집 패널 비활성화
        if len(self._get_selected_rows()) > 1:
            self.text_subtitle_edit.setEnabled(False)
            self.btn_subtitle_confirm.setEnabled(False)
            self._time_edit_start.setEnabled(False)
            self._time_edit_end.setEnabled(False)
            self._btn_reset.setEnabled(False)
            return

        # 비디오 재생 중 자동 선택된 경우 seek 무시
        if not getattr(self, "_is_auto_selecting", False):
            seg = self._segments[row]
            self._video_player.seek(seg.get('start', 0))

        seg = self._segments[row]
        text = seg.get("text", "")
        self.text_subtitle_edit.setPlainText(text)
        self.text_subtitle_edit.setEnabled(True)
        self.btn_subtitle_confirm.setEnabled(True)
        self._btn_reset.setEnabled(bool(self._original_segments))

        self._time_edit_start.setTime(_ms_to_qtime(seg.get("start", 0)))
        self._time_edit_end.setTime(_ms_to_qtime(seg.get("end", 0)))
        self._time_edit_start.setEnabled(True)
        self._time_edit_end.setEnabled(True)

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

            new_start = _qtime_to_ms(self._time_edit_start.time())
            new_end   = _qtime_to_ms(self._time_edit_end.time())
            self._apply_time_edit(row, new_start, new_end)

    def _reset_segment(self):
        row = self.list_segments.currentRow()
        if row < 0 or row >= len(self._segments) or row >= len(self._original_segments):
            return

        orig = self._original_segments[row]
        self._segments[row]["text"]  = orig.get("text", "")
        self._segments[row]["start"] = orig["start"]
        self._segments[row]["end"]   = orig["end"]

        # UI 갱신
        item = self.list_segments.item(row, 3)
        if item:
            item.setText(orig.get("text", ""))
        self._update_table_time(row)
        self.text_subtitle_edit.setPlainText(orig.get("text", ""))
        self._time_edit_start.setTime(_ms_to_qtime(orig["start"]))
        self._time_edit_end.setTime(_ms_to_qtime(orig["end"]))

        # 인접 구간 경계도 원본으로 복원
        if row > 0:
            self._segments[row - 1]["end"] = orig["start"]
            self._update_table_time(row - 1)
        if row < len(self._segments) - 1:
            self._segments[row + 1]["start"] = orig["end"]
            self._update_table_time(row + 1)

        duration_ms = max(s["end"] for s in self._segments)
        self._waveform.set_segments(self._segments, duration_ms)

    def _merge_segments(self):
        rows = self._get_selected_rows()
        if len(rows) < 2:
            return

        if rows != list(range(rows[0], rows[-1] + 1)):
            QMessageBox.warning(self, "병합 오류", "연속된 구간만 병합할 수 있습니다.")
            return

        merged = {
            "start": self._segments[rows[0]]["start"],
            "end":   self._segments[rows[-1]]["end"],
            "text":  " ".join(
                self._segments[r].get("text", "").strip()
                for r in rows
                if self._segments[r].get("text", "").strip()
            ),
            "keep": True,
        }

        del self._segments[rows[0]: rows[-1] + 1]
        self._segments.insert(rows[0], merged)

        self._populate_segments(self._segments)
        self.list_segments.selectRow(rows[0])

    def _apply_time_edit(self, row: int, new_start: int, new_end: int):
        seg = self._segments[row]

        if new_start >= new_end:
            QMessageBox.warning(self, "시간 오류", "시작 시간이 종료 시간보다 크거나 같습니다.")
            return
        if row > 0 and new_start <= self._segments[row - 1]["start"]:
            QMessageBox.warning(self, "시간 오류", "이전 구간을 소멸시킬 수 없습니다.")
            return
        if row < len(self._segments) - 1 and new_end >= self._segments[row + 1]["end"]:
            QMessageBox.warning(self, "시간 오류", "다음 구간을 소멸시킬 수 없습니다.")
            return

        if row > 0:
            self._segments[row - 1]["end"] = new_start
            self._update_table_time(row - 1)
        if row < len(self._segments) - 1:
            self._segments[row + 1]["start"] = new_end
            self._update_table_time(row + 1)

        seg["start"] = new_start
        seg["end"]   = new_end
        self._update_table_time(row)

        duration_ms = max(s["end"] for s in self._segments)
        self._waveform.set_segments(self._segments, duration_ms)

    def _update_table_time(self, row: int):
        seg = self._segments[row]
        item = self.list_segments.item(row, 0)
        if item:
            item.setText(f"{format_time(seg['start'])} ~ {format_time(seg['end'])}")

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
            "silence_threshold": float(s.value("silence_threshold", 0.5)),
            "min_silence_ms": int(s.value("min_silence_ms", 500)),
            "whisper_model": int(s.value("whisper_model", 3)),
        }


def _ms_to_qtime(ms: int) -> QTime:
    return QTime(0, ms // 60000, (ms % 60000) // 1000, ms % 1000)


def _qtime_to_ms(t: QTime) -> int:
    return t.minute() * 60000 + t.second() * 1000 + t.msec()
