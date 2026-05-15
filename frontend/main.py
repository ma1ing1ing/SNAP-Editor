import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.uic import loadUi
from settings_dialog import SettingsDialog


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_window.ui")
        loadUi(ui_path, self)

        self.video_path = None

        self.setup_connections()    # 버튼 연결 함수 호출

    def setup_connections(self):     # 모든 버튼/위젯 연결
        self.btn_open_file.clicked.connect(self.open_file)
        self.btn_settings.clicked.connect(self.open_settings)
        # 나중에 다른 버튼들도 여기에 추가
        # self.btn_play.clicked.connect(self.play_video)
        # self.btn_start_process.clicked.connect(self.start_analysis)

    def open_file(self):

        path, _ = QFileDialog.getOpenFileName(
            self,
            "영상 파일 선택",     # 창 제목
            "",
            "Videos (*.mp4 *.mov *.avi *.mkv)"  # 선택 가능한 파일 형식
        )

        if path:
            self.video_path = path
            self.label_file_path.setText(path)
            self.label_status.setText("파일 로드 완료")
            self.btn_render.setEnabled(True)

    def open_settings(self):   # label_status를 업데이트
        dialog = SettingsDialog(parent=self)
        dialog.exec()
        self.label_status.setText("설정 저장 완료")


#
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())