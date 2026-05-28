from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QPolygon, QPainterPath


class WaveformWidget(QWidget):
    """
    오디오 파형 + 편집 구간 타임라인 위젯.
      - 초록/빨강 반투명 배경: keep=True/False 구간
      - 흰색 수직선: 진폭 파형 (oscilloscope 형태)
      - 노란 반투명 오버레이: 현재 선택된 구간
      - 흰 세로선 + 삼각형: 재생 위치 playhead
    """

    _COLOR_BG        = QColor("#1e1e2e")
    _COLOR_KEEP_BG   = QColor(76, 175, 80, 55)
    _COLOR_REMOVE_BG = QColor(239, 83, 80, 55)
    _COLOR_WAVEFORM  = QColor(210, 215, 240, 210)
    _COLOR_SELECT    = QColor(255, 220, 50, 80)
    _COLOR_PLAYHEAD  = QColor("#ffffff")
    _COLOR_TICK      = QColor(100, 100, 140, 100)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(80)

        self._segments: list[dict] = []
        self._duration_ms: int = 0
        self._selected_index: int = -1
        self._position_ms: int = 0
        self._amplitudes: list[float] = []

    # ── 외부 API ──────────────────────────────────────────────────────────────

    def set_segments(self, segments: list[dict], duration_ms: int):
        self._segments = segments
        self._duration_ms = max(duration_ms, 1)
        self._selected_index = -1
        self.update()

    def set_waveform(self, amplitudes: list[float], duration_ms: int):
        self._amplitudes = amplitudes
        self._duration_ms = max(duration_ms, 1)
        self.update()

    def set_selected(self, index: int):
        self._selected_index = index
        self.update()

    def set_position(self, position_ms: int):
        self._position_ms = position_ms
        self.update()

    def update_keep(self, index: int, keep: bool):
        if 0 <= index < len(self._segments):
            self._segments[index]["keep"] = keep
            self.update()

    # ── 렌더링 ────────────────────────────────────────────────────────────────

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # 배경
        p.fillRect(0, 0, w, h, self._COLOR_BG)

        if not self._segments or self._duration_ms <= 0:
            self._draw_playhead(p, w, h)
            return

        # 구간 배경 (반투명 초록/빨강)
        for seg in self._segments:
            x1 = self._ms_to_x(seg.get("start", 0), w)
            x2 = self._ms_to_x(seg.get("end", 0), w)
            color = self._COLOR_KEEP_BG if seg.get("keep", True) else self._COLOR_REMOVE_BG
            p.fillRect(x1, 0, max(x2 - x1, 2), h, color)

        # 파형
        if self._amplitudes:
            self._draw_waveform(p, w, h)

        # 선택 구간 오버레이
        if 0 <= self._selected_index < len(self._segments):
            seg = self._segments[self._selected_index]
            x1 = self._ms_to_x(seg.get("start", 0), w)
            x2 = self._ms_to_x(seg.get("end", 0), w)
            p.fillRect(x1, 0, max(x2 - x1, 2), h, self._COLOR_SELECT)
            p.setPen(QPen(QColor(255, 220, 50, 200), 1, Qt.PenStyle.DashLine))
            p.drawLine(x1, 0, x1, h)
            p.drawLine(x2, 0, x2, h)

        # 시간 눈금 (하단)
        p.setPen(QPen(self._COLOR_TICK, 1))
        for i in range(1, 10):
            tick_x = int(w * i / 10)
            p.drawLine(tick_x, h - 6, tick_x, h)

        self._draw_playhead(p, w, h)

    def _draw_waveform(self, p: QPainter, w: int, h: int):
        mid = h // 2
        n = len(self._amplitudes)
        p.setPen(QPen(self._COLOR_WAVEFORM, 1))
        for px in range(w):
            idx = min(int(px / w * n), n - 1)
            amp = self._amplitudes[idx]
            half = int(amp * (mid - 4))
            if half > 0:
                p.drawLine(px, mid - half, px, mid + half)

    def _draw_playhead(self, p: QPainter, w: int, h: int):
        if self._duration_ms <= 0:
            return
        x = self._ms_to_x(self._position_ms, w)
        p.setPen(QPen(self._COLOR_PLAYHEAD, 2))
        p.drawLine(x, 0, x, h)

        p.setBrush(self._COLOR_PLAYHEAD)
        p.setPen(Qt.PenStyle.NoPen)
        poly = QPolygon([QPoint(x - 5, 0), QPoint(x + 5, 0), QPoint(x, 8)])
        p.drawPolygon(poly)

    def _ms_to_x(self, ms: int, width: int) -> int:
        return int(ms / self._duration_ms * width)
