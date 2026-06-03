import os
import sys


def resource_path(*parts: str) -> str:
    """
    리소스 파일의 절대 경로 반환.
    - 개발 환경: frontend/ 기준 경로
    - PyInstaller 번들: sys._MEIPASS 기준 경로
    """
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        # frontend/utils/resource_path.py → 상위 1단계 = frontend/
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)
