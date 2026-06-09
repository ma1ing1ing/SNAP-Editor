# SNAP-Editor 팀원 역할 분담 및 수행 내용

> **S**mart **N**eat **A**utomated **P**rocessing  
> AI 기반 자동 영상 편집 및 자막 생성 도구

---

| 이름 | 담당 역할 | 수행 내용 |
|------|-----------|-----------|
| 박마린 | 프론트엔드 개발 및 프로젝트 총괄 | PyQt6 기반 GUI 전체 설계·구현, QThread 비동기 Worker 아키텍처 구성, YouTube 다운로드 연동, PyInstaller macOS 배포 패키징 |
| 이동이 | AI NLP 모듈 개발 | Kiwi 형태소 분석기 기반 STT 결과 후처리 로직 구현 및 한국어 불용어 사전(`stopwords_ko.json`) 구축 |
| 정규상 | AI-백엔드 연동 파이프라인 설계 | AI 필터링 파이프라인 모듈화, STT segment 데이터 형식 표준화, 백엔드 진행률 콜백 구조 설계 |
| 장규민 | 백엔드 핵심 개발 (STT·렌더링) | `backend_controller.py` 설계, stable-whisper 기반 STT 및 자막 싱크 구현, FFmpeg 렌더링 최적화 |
| 장경민 | 백엔드 개발 (VAD·JSON 추출) | Silero VAD 기반 무음 구간 감지 로직 구현, 분석 결과 JSON 직렬화, 자막·오디오 싱크 조정 |

---

*git 커밋 이력 전수 분석 기반으로 작성 (2026-06-07)*
