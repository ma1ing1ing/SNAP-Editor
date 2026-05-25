from PyQt6.QtCore import QObject, pyqtSignal, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtWidgets import QVBoxLayout


class VideoPlayer(QObject):

    position_changed = pyqtSignal(int, int)  # (현재 위치 ms, 전체 길이 ms)

    def __init__(self, video_frame):
        super().__init__()

        self._video_frame = video_frame
        self._is_seeking = False
        self._preview_on_load = False

        self._player = QMediaPlayer()
        self._audio = QAudioOutput()
        self._player.setAudioOutput(self._audio)

        self._video_widget = QVideoWidget()
        self._player.setVideoOutput(self._video_widget)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._video_widget)
        self._video_frame.setLayout(layout)

        self._player.positionChanged.connect(self._on_position_changed)
        self._player.playbackStateChanged.connect(self._on_playback_state_changed)

    def _on_position_changed(self, position: int):
        if self._is_seeking:
            return
        duration = self._player.duration()
        self.position_changed.emit(position, duration)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        if state == QMediaPlayer.PlaybackState.PlayingState and self._preview_on_load:
            self._preview_on_load = False
            self._player.pause()

    def play(self):
        self._player.play()

    def pause(self):
        self._player.pause()

    def seek(self, position: int):
        self._player.setPosition(position)

    def load(self, file_path: str):
        self._preview_on_load = True
        self._player.setSource(QUrl.fromLocalFile(file_path))

    def set_seeking(self, is_seeking: bool):
        self._is_seeking = is_seeking
