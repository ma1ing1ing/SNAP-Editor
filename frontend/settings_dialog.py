import os
from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QSettings
from PyQt6.uic import loadUi


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings_dialog.ui")
        loadUi(ui_path, self)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save_settings.clicked.connect(self.save_settings)
        self.btn_add_word.clicked.connect(self.add_word)

        self.load_settings()

    def load_settings(self):
        settings = QSettings("SNAP", "Editor")
        self.spin_silence_threshold.setValue(float(settings.value("silence_threshold", 0.5)))
        self.combo_whisper_model.setCurrentIndex(int(settings.value("whisper_model", 3)))

    def save_settings(self):
        settings = QSettings("SNAP", "Editor")
        settings.setValue("silence_threshold", self.spin_silence_threshold.value())
        settings.setValue("whisper_model", self.combo_whisper_model.currentIndex())
        self.accept()

    def add_word(self): # 공백 제거 후 비워있지 않을떄만 추가
        text = self.input_word.text().strip()
        if text:
            self.list_words.addItem(text)
            self.input_word.clear()
