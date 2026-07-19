from PyQt6.QtWidgets import QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QSize


class ElidingLabel(QLabel):
    """sizeHint()를 작게 고정해 창 확장을 막고, 텍스트를 자동 엘리딩하는 QLabel."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def sizeHint(self):
        return QSize(200, super().sizeHint().height())

    def minimumSizeHint(self):
        return QSize(0, super().minimumSizeHint().height())

    def setText(self, text: str):
        self._full_text = text
        self._elide()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._elide()

    def _elide(self):
        if not self._full_text:
            super().setText("")
            return
        w = self.width()
        if w <= 0:
            return
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideMiddle, w
        )
        super().setText(elided)
