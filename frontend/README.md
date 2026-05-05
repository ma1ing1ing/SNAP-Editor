# Frontend
 
PyQt6 기반 데스크탑 GUI 로컬 앱. 
Qt Designer로 설계됨.

---

## 파일 구조

frontend/
├── main.py                    # 앱 실행 진입점
├── main_window.ui             # 메인 화면 레이아웃
├── settings_dialog.ui         # 설정 팝업
├── alert_popup.ui             # AI 분석 완료 알림 팝업
└── render_complete_popup.ui   # 렌더링 완료 알림 팝업


## 현재 상태 / TODO
 
**완료**
- ui 창
**미완성**
- 버튼 클릭 이벤트 연결 (시그널/슬롯)
- 영상 재생 기능 (QMediaPlayer 임베드)
- AI/BE 파이프라인 호출 및 결과 표시
- 타임라인 파형 시각화
- 설정값 저장 및 AI 파라미터 전달
