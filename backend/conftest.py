"""pytest 전역 설정 - 테스트 세션 동안 uvicorn 서버를 자동으로 시작/종료"""
import atexit
import os
import threading
import time

# 독립 실행 스크립트를 pytest 수집에서 제외
import dev_db_guard as _guard

collect_ignore = list(_guard.STANDALONE_SCRIPTS)

import pytest
import requests
import uvicorn


# ★requests 에 기본 타임아웃을 건다. 테스트 354개 호출에 timeout 인자가 하나도 없어
#   서버가 굳으면 스위트가 영원히 매달린다(2026-09-05 실측: 600초 타임아웃에 걸림).
#   여기서 한 번 감싸면 호출부를 354곳 고치지 않아도 된다.
_DEFAULT_TIMEOUT = float(os.getenv("TEST_HTTP_TIMEOUT", "30"))
_orig_request = requests.Session.request


def _request_with_timeout(self, method, url, **kw):
    kw.setdefault("timeout", _DEFAULT_TIMEOUT)
    return _orig_request(self, method, url, **kw)


requests.Session.request = _request_with_timeout


# ★주소는 127.0.0.1 을 쓴다. Windows 에서 localhost 는 ::1 과 127.0.0.1 둘 다로
#   풀리는데 uvicorn 은 IPv4 로만 듣는다. 그래서 매 요청이 IPv6 시도에서 2초를 버렸다
#   (실측 2046ms -> 2ms, 스위트 18분 39초 -> 1분대).
def _server_already_running(port: int) -> bool:
    """이미 서버가 해당 포트에서 실행 중인지 확인"""
    try:
        r = requests.get(f"http://127.0.0.1:{port}/", timeout=2)
        return r.status_code < 500
    except requests.exceptions.RequestException:
        return False


# ★DATABASE_URL 은 conftest 를 임포트하는 시점에 정한다. 픽스처 안은 늦다.
#   `database.py` 는 임포트 시점에 engine 을 만드는데, 테스트 모듈이 모듈 수준에서
#   `models` 를 임포트하면(tests_unit/test_tc_id_dedup.py) 수집 단계에서 이미
#   engine 이 셸이나 .env 의 주소에 묶인다. 그러면 lifespan(실행 시점에
#   os.getenv 를 읽는다)은 임시 DB 로 마이그레이션하고 앱 세션은 개발 DB 를 본다
#   (2026-09-07 실측: CI 223 errors, 로컬 184 errors).
#   conftest 는 어떤 테스트 모듈보다 먼저 임포트되므로 여기가 유일하게 안전한 자리다.
TEST_PORT = int(os.getenv("TEST_PORT", "8008"))

# ★테스트가 실제로 요청을 보내는 곳은 TEST_BASE_URL 이다. 서버를 띄우는 포트와
#   갈라질 수 있어서(TEST_PORT 는 비어 있는데 요청은 개발 서버로 가는 식), 개발 DB
#   위험 판정은 이쪽을 본다.
def _request_port() -> int:
    """테스트가 실제로 요청을 보내는 포트. 기본값은 dev_db_guard 가 들고 있다."""
    from urllib.parse import urlparse

    import dev_db_guard as _guard

    base = os.getenv("TEST_BASE_URL")
    if not base:
        return _guard.DEFAULT_REQUEST_PORT
    return urlparse(base).port or 80

import testing_db

#: 개발 서버가 이미 떠 있으면 HTTP 는 그 서버의 DB 로 간다. 그때 in-process engine 만
#: 임시 DB 로 돌리면 한 테스트가 두 DB 를 보게 되므로 손대지 않는다.
USING_RUNNING_DEV_SERVER = _server_already_running(TEST_PORT)

SESSION_DATABASE_URL = None
SESSION_DATABASE_NAME = None


def _isolate_database_url():
    """세션 전용 임시 DB 를 만들고 DATABASE_URL 을 거기로 박는다.

    ★셸이나 .env 의 DATABASE_URL 은 보지 않는다. 운영 주소가 들어 있어도 쓰지 않는다.
      관리 주소(TEST_DATABASE_ADMIN_URL)는 testing_db 가 로컬 호스트만 허용한다.
      SQLite 시절에는 `/tc_manager.db` 로 끝나는 주소만 격리해서, 다른 주소는 그대로 썼다.
    ★스키마는 alembic upgrade 로 올린다. 서버가 lifespan 에서 다시 upgrade 해도 이미
      head 라 아무 일도 없다. create_all 이 아니라 기준점으로 올려야 마이그레이션도 검증된다.
    """
    global SESSION_DATABASE_URL, SESSION_DATABASE_NAME
    if USING_RUNNING_DEV_SERVER:
        return
    import subprocess
    import sys

    from sqlalchemy.engine import make_url

    url = testing_db.create_database(prefix="ymtc_test")
    atexit.register(testing_db.drop_database, url)
    os.environ["DATABASE_URL"] = url
    # ★지우지 않고 빈 값으로 박는다. 키가 없으면 하위 프로세스(alembic)와 이후의
    #   database 임포트에서 dotenv 가 `.env` 의 운영 직결 주소를 다시 채우고, env.py 는
    #   그 주소를 우선해 운영 DB 에 마이그레이션을 시도한다(2026-10-08 재현). 빈 값은
    #   load_dotenv(override=False) 가 덮지 않는다.
    os.environ["DATABASE_URL_DIRECT"] = ""
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=os.path.dirname(os.path.abspath(__file__)),
                       env=dict(os.environ), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("테스트 DB 마이그레이션 실패: " + r.stderr)
    SESSION_DATABASE_URL = url
    SESSION_DATABASE_NAME = make_url(url).database


_isolate_database_url()

# 개발 DB 를 건드릴 위험이 실제로 있는지 알린다. 테스트 파일이 이 값으로 건너뛴다.
#
# ★포트 번호로 판정하면 안 된다. 기본 포트가 8008 이라는 이유로 건너뛰던 파일들이
#   있었는데, 개발 서버가 안 떠 있으면 위 코드가 임시 DB 를 잡고 8008 에 격리 서버를
#   직접 띄운다. 즉 그 상황은 위험하지 않다. 그런데도 건너뛰는 바람에 CI 에서 40건이
#   한 줄도 실행되지 않았다(실측: 기본 수집 262건, TEST_PORT=8009 수집 302건).
#   위험한 것은 "이미 떠 있는 개발 서버를 그대로 쓰는" 경우뿐이다.
import dev_db_guard

dev_db_guard.USING_RUNNING_DEV_SERVER = USING_RUNNING_DEV_SERVER
dev_db_guard.SESSION_DATABASE_NAME = SESSION_DATABASE_NAME
dev_db_guard.DEV_DB_AT_RISK = (
    _server_already_running(_request_port()) and os.getenv("ALLOW_DEV_DB") != "1"
)


def _wait_for_server(url: str, timeout: float = 15):
    """서버가 응답할 때까지 대기"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.3)
    raise RuntimeError(f"Server did not start within {timeout}s at {url}")


def _seed_admin(base_url: str, password: str):
    """admin 계정이 없으면 등록"""
    r = requests.post(f"{base_url}/api/auth/register", json={
        "username": "admin",
        "password": password,
        "display_name": "Admin",
    })
    # 201 = 새로 생성, 400 = 이미 존재 - 둘 다 OK
    if r.status_code not in (201, 400):
        raise RuntimeError(f"Admin seed failed: {r.status_code} {r.text}")


@pytest.fixture(scope="session", autouse=True)
def _server():
    """세션 시작 시 uvicorn 서버를 백그라운드 스레드로 실행 (이미 실행 중이면 스킵)"""
    port = int(os.getenv("TEST_PORT", "8008"))
    admin_pw = os.getenv("TEST_ADMIN_PASSWORD", "test1234")
    base_url = f"http://127.0.0.1:{port}"

    if _server_already_running(port):
        import warnings
        warnings.warn(
            f"Using already-running server at port {port} - tests are NOT isolated (no temp DB)",
            stacklevel=2,
        )
        # ★이미 떠 있는 서버의 DB 는 어디인지 모른다(운영일 수도 있다). 시드도 쓰기라
        #   일부러 허용(ALLOW_DEV_DB=1)했을 때만 한다.
        if os.getenv("ALLOW_DEV_DB") == "1":
            _seed_admin(base_url, admin_pw)
        yield
        return

    # 임시 DB 는 이 파일 맨 위에서 이미 DATABASE_URL 에 박아 두었다.
    # 여기서 다시 변경하면 수집 단계에 만들어진 engine 과 갈라진다.
    from main import app

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    _wait_for_server(f"{base_url}/docs")

    # admin 계정 시드
    _seed_admin(base_url, admin_pw)

    yield
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def pg_engine():
    """테스트 하나 전용 스키마. SQLite 시절 tmp_path 마다 새 DB 파일을 만들던 자리다."""
    base = SESSION_DATABASE_URL or testing_db.create_database(prefix="ymtc_unit")
    eng = None
    try:
        eng = testing_db.schema_engine(base)
        yield eng
    finally:
        try:
            if eng is not None:
                testing_db.dispose_schema_engine(eng)
        finally:
            if SESSION_DATABASE_URL is None:
                testing_db.drop_database(base)


@pytest.fixture
def pg_session(pg_engine):
    from sqlalchemy.orm import sessionmaker

    session = sessionmaker(bind=pg_engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
