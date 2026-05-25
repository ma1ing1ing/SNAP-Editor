from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QFont


class WaveformWidget(QWidget):
    """
    타임라인 바 위에 편집 구간을 시각화하는 위젯.
      - 초록 블록: keep=True 구간
      - 빨간 블록: keep=False 구간
      - 노란 반투명 오버레이: 현재 선택된 구간
      - 흰 세로선: 재생 위치 playhead
    """

    _COLOR_BG       = QColor("#1e1e2e")
    _COLOR_TRACK    = QColor("#2e2e4e")
    _COLOR_KEEP     = QColor("#4caf50")
    _COLOR_REMOVE   = QColor("#ef5350")
    _COLOR_SELECT   = QColor(255, 220, 50, 90)   # 노란 반투명
    _COLOR_PLAYHEAD = QColor("#ffffff")
    _COLOR_BORDER   = QColor("#555577")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(60)

        self._segments: list[dict] = []
        self._duration_ms: int = 0
        self._selected_index: int = -1
        self._position_ms: int = 0

    # ── 외부 API ──────────────────────────────────────────────────────────────

    def set_segments(self, segments: list[dict], duration_ms: int):
        self._segments = segments
        self._duration_ms = max(duration_ms, 1)
        self._selected_index = -1
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
        track_y = h // 2 - 10
        track_h = 20

        # 배경
        p.fillRect(0, 0, w, h, self._COLOR_BG)

        # 트랙 바
        p.fillRect(0, track_y, w, track_h, self._COLOR_TRACK)
        p.setPen(QPen(self._COLOR_BORDER, 1))
        p.drawRect(0, track_y, w - 1, track_h - 1)

        if not self._segments or self._duration_ms <= 0:
            self._draw_playhead(p, w, h)
            return

        # 구간 블록
        for i, seg in enumerate(self._segments):
            x1 = self._ms_to_x(seg.get("start", 0), w)
            x2 = self._ms_to_x(seg.get("end", 0), w)
            block_w = max(x2 - x1, 2)

            color = self._COLOR_KEEP if seg.get("keep", True) else self._COLOR_REMOVE
            p.fillRect(x1, track_y + 2, block_w, track_h - 4, color)

        # 선택 구간 하이라이트 (전체 높이에 반투명 오버레이)
        if 0 <= self._selected_index < len(self._segments):
            seg = self._segments[self._selected_index]
            x1 = self._ms_to_x(seg.get("start", 0), w)
            x2 = self._ms_to_x(seg.get("end", 0), w)
            p.fillRect(x1, 0, max(x2 - x1, 2), h, self._COLOR_SELECT)

            # 선택 구간 양쪽 경계선
            p.setPen(QPen(QColor(255, 220, 50, 200), 1, Qt.PenStyle.DashLine))
            p.drawLine(x1, 0, x1, h)
            p.drawLine(x2, 0, x2, h)

        # 시간 눈금 (10% 간격)
        p.setPen(QPen(QColor(100, 100, 140, 120), 1))
        for i in range(1, 10):
            tick_x = int(w * i / 10)
            p.drawLine(tick_x, track_y + track_h, tick_x, track_y + track_h + 4)

        self._draw_playhead(p, w, h)

    def _draw_playhead(self, p: QPainter, w: int, h: int):
        if self._duration_ms <= 0:
            return
        x = self._ms_to_x(self._position_ms, w)
        p.setPen(QPen(self._COLOR_PLAYHEAD, 2))
        p.drawLine(x, 0, x, h)

        # 삼각형 헤드
        p.setBrush(self._COLOR_PLAYHEAD)
        p.setPen(Qt.PenStyle.NoPen)
        points_x = [x - 5, x + 5, x]
        points_y = [0, 0, 8]
        from PyQt6.QtGui import QPolygon
        from PyQt6.QtCore import QPoint
        poly = QPolygon([QPoint(px, py) for px, py in zip(points_x, points_y)])
        p.drawPolygon(poly)

    def _ms_to_x(self, ms: int, width: int) -> int:
        return int(ms / self._duration_ms * width)
