"""테스트용 PostgreSQL 접속을 한 곳에서 만든다.

서버 테스트는 세션마다 임시 데이터베이스를, 단위 테스트는 테스트마다 임시 스키마를
쓴다. 둘 다 이 모듈을 거친다.

★관리 주소의 호스트가 로컬이 아니면 거부한다. `.env` 에 운영 Supabase 주소가 들어
  있는 채로 pytest 를 돌려도 테스트가 그 DB 를 만지지 못하게 하는 것이 이 모듈의
  첫째 일이다. SQLite 시절의 `/tc_manager.db` 접미사 판정을 대신한다.
"""
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

DEFAULT_ADMIN_URL = "postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def admin_url() -> str:
    url = os.getenv("TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_URL)
    parsed = make_url(url)
    if parsed.host not in _LOCAL_HOSTS:
        raise RuntimeError(f"테스트 DB 는 로컬 호스트만 허용한다: {parsed.host}")
    # ★쿼리 옵션도 막는다. libpq 는 `?host=`, `?hostaddr=`, `?service=` 로 실제 접속
    #   대상을 바꾼다. 주소의 호스트 부분만 보면 로컬처럼 보이는 원격 주소를 통과시킨다.
    if parsed.query:
        raise RuntimeError(f"테스트 DB 관리 주소에 쿼리 옵션을 쓸 수 없다(로컬 판정 우회 방지): {dict(parsed.query)}")
    return url


def _admin_engine() -> Engine:
    return create_engine(admin_url(), isolation_level="AUTOCOMMIT")


def create_database(prefix: str = "ymtc_test") -> str:
    name = f"{prefix}_{uuid.uuid4().hex[:10]}"
    eng = _admin_engine()
    try:
        with eng.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        eng.dispose()
    return make_url(admin_url()).set(database=name).render_as_string(hide_password=False)


def drop_database(url: str) -> None:
    name = make_url(url).database
    eng = _admin_engine()
    try:
        with eng.connect() as c:
            c.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                     "WHERE datname = :n AND pid <> pg_backend_pid()"),
                {"n": name},
            )
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        eng.dispose()


def schema_engine(base_url: str) -> Engine:
    """임시 스키마 하나를 만들고 그 안에 현재 모델의 테이블을 만든 엔진.

    enum 타입도 `search_path` 의 첫 스키마에 생기므로 테스트끼리 섞이지 않는다.
    """
    import models  # noqa: F401  Base 에 테이블을 등록한다
    from database import Base

    schema = f"t_{uuid.uuid4().hex[:12]}"
    boot = create_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        with boot.connect() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        boot.dispose()
    eng = create_engine(base_url, connect_args={"options": f"-csearch_path={schema}"})
    eng._ymtc_schema = schema
    Base.metadata.create_all(eng)
    return eng


def dispose_schema_engine(engine: Engine) -> None:
    schema = engine._ymtc_schema
    url = engine.url
    engine.dispose()
    boot = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with boot.connect() as c:
            c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        boot.dispose()
