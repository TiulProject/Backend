# 1주차에는 모듈이 에러 나지 않도록 빈 파일 상태나 기본 임포트만 유지해 둡니다.
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")