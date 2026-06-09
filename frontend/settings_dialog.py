from PyQt6.QtWidgets import QDialog
from PyQt6.QtCore import QSettings
from PyQt6.uic import loadUi
from utils.resource_path import resource_path

_SETTINGS_KEY_WORDS = "highlight_words"


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        loadUi(resource_path("settings_dialog.ui"), self)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save_settings.clicked.connect(self.save_settings)
        self.btn_add_word.clicked.connect(self.add_word)
        self.btn_remove_word.clicked.connect(self.remove_word)
        self.input_word.returnPressed.connect(self.add_word)

        self.load_settings()

    def load_settings(self):
        settings = QSettings("SNAP", "Editor")
        min_silence_ms = int(settings.value("min_silence_ms", 500))
        self.spin_silence_threshold.setValue(min_silence_ms / 1000.0)
        self.combo_whisper_model.setCurrentIndex(int(settings.value("whisper_model", 3)))

        self.list_words.clear()
        saved = settings.value(_SETTINGS_KEY_WORDS, "")
        for word in [w.strip() for w in saved.split(",") if w.strip()]:
            self.list_words.addItem(word)

    def save_settings(self):
        settings = QSettings("SNAP", "Editor")
        settings.setValue("min_silence_ms", int(self.spin_silence_threshold.value() * 1000))
        settings.setValue("whisper_model", self.combo_whisper_model.currentIndex())

        words = [self.list_words.item(i).text() for i in range(self.list_words.count())]
        settings.setValue(_SETTINGS_KEY_WORDS, ",".join(words))

        self.accept()

    def add_word(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.inputMethod().commit()
        text = self.input_word.text().strip()
        if not text:
            return
        existing = [self.list_words.item(i).text() for i in range(self.list_words.count())]
        if text not in existing:
            self.list_words.addItem(text)
        self.input_word.clear()

    def remove_word(self):
        for item in self.list_words.selectedItems():
            self.list_words.takeItem(self.list_words.row(item))
