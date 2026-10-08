# .env 로딩 - 아래 os.getenv 호출보다 먼저 실행되어야 한다
import env_setup  # noqa: F401

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool


def require_database_url() -> str:
    """DATABASE_URL 을 읽는다. 없거나 SQLite 면 멈춘다.

    ★기본값을 두지 않는다. 기본값이 있으면 주소 전달이 빠진 배포가 로컬 파일 DB 에
      조용히 성공한다. 실패가 늦게 드러나는 것보다 지금 멈추는 편이 싸다.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 이 설정되지 않았다. backend/.env.example 참고")
    if url.startswith("sqlite"):
        raise RuntimeError(
            "SQLite 는 더 지원하지 않는다. PostgreSQL 주소를 쓴다. "
            "SQLite 버전은 sqlite-legacy 브랜치(v1.10.3.1)"
        )
    return url


DATABASE_URL = require_database_url()

_engine_kwargs = {"pool_pre_ping": True}
# 서버리스는 실행 환경이 수시로 생기고 사라져 풀을 들고 있을 이유가 없다.
# 연결 재사용은 Supabase 풀러가 맡는다.
from services.runtime_env import env_value  # noqa: E402

if env_value("DB_POOL") == "null":
    _engine_kwargs["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
