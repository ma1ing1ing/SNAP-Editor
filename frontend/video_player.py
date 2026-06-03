from PyQt6.QtCore import QObject, pyqtSignal, QUrl, Qt, QEvent
from PyQt6.QtGui import QPixmap
from utils.resource_path import resource_path
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QLabel, QStackedLayout


class VideoPlayer(QObject):

    position_changed = pyqtSignal(int, int)   # (현재 위치 ms, 전체 길이 ms)
    playing_changed  = pyqtSignal(bool)        # True=재생 중, False=정지/일시정지

    def __init__(self, video_frame):
        super().__init__()

        self._video_frame = video_frame
        self._is_seeking = False
        self._preview_on_load = False
        self._placeholder_pixmap = QPixmap(resource_path("icons", "ready_placeholder.png"))

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)

        self._placeholder = QLabel()
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("background-color: #000;")
        self._placeholder.installEventFilter(self)

        self._video_widget = QVideoWidget()
        self._video_widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self._player.setVideoOutput(self._video_widget)

        self._stack = QStackedLayout()
        self._stack.setContentsMargins(0, 0, 0, 0)
        self._stack.addWidget(self._placeholder)
        self._stack.addWidget(self._video_widget)
        self._video_frame.setLayout(self._stack)
        self._stack.setCurrentWidget(self._placeholder)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)
        self._update_placeholder_pixmap()

    def eventFilter(self, obj, event):
        if obj is self._placeholder and event.type() == QEvent.Type.Resize:
            self._update_placeholder_pixmap()
        return super().eventFilter(obj, event)

    def _update_placeholder_pixmap(self):
        if self._placeholder_pixmap.isNull():
            return

        width = max(1, int(self._placeholder.width() * 0.78))
        height = max(1, int(self._placeholder.height() * 0.78))
        self._placeholder.setPixmap(
            self._placeholder_pixmap.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _on_position_changed(self, position: int):
        if self._is_seeking:
            return
        duration = self._player.duration()
        self.position_changed.emit(position, duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState and self._preview_on_load:
            self._preview_on_load = False
            self._player.pause()
        self.playing_changed.emit(state == QMediaPlayer.PlaybackState.PlayingState)

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def toggle(self):
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def seek(self, position: int):
        self._player.setPosition(position)

    def load(self, file_path: str):
        self._stack.setCurrentWidget(self._video_widget)
        self._preview_on_load = True
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.setSource(QUrl.fromLocalFile(file_path))

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
            self._player.mediaStatusChanged.disconnect(self._on_media_status_changed)
            self._player.play()

    def set_seeking(self, is_seeking: bool):
        self._is_seeking = is_seeking

    @property
    def video_widget(self):
        return self._video_widget
