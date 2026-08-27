"""backend/.env 를 프로세스 환경변수로 로드한다.

os.getenv 를 모듈 로드 시점에 읽는 모듈(auth, database, main)보다 반드시
먼저 임포트되어야 한다. 그래서 각 모듈 최상단에서 이 모듈을 임포트한다.

override=False 이므로 이미 설정된 환경변수는 덮어쓰지 않는다.
테스트(conftest)가 미리 지정한 DATABASE_URL 이나 배포 환경의 실제
환경변수가 .env 파일보다 항상 우선한다.

ENV_FILE 로 다른 경로를 지정할 수 있다(배포 환경, 테스트용).
"""
import os

from dotenv import load_dotenv

ENV_FILE = os.getenv("ENV_FILE") or os.path.join(os.path.dirname(__file__), ".env")

load_dotenv(ENV_FILE)
