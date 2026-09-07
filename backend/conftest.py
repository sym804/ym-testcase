"""pytest 전역 설정 - 테스트 세션 동안 uvicorn 서버를 자동으로 시작/종료"""
import atexit
import os
import shutil
import tempfile
import threading
import time

# 독립 실행 스크립트를 pytest 수집에서 제외
collect_ignore = ["test_v060_full.py", "test_v060_edge_cases.py", "test_v103_features.py", "test_v110_features.py"]

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
#   engine 이 기본값인 개발용 tc_manager.db 에 묶인다. 그러면 lifespan(실행 시점에
#   os.getenv 를 읽는다)은 임시 DB 로 마이그레이션하고 앱 세션은 개발 DB 를 본다
#   (2026-09-07 실측: CI 223 errors, 로컬 184 errors).
#   conftest 는 어떤 테스트 모듈보다 먼저 임포트되므로 여기가 유일하게 안전한 자리다.
DEV_DB_SUFFIX = "/tc_manager.db"
TEST_PORT = int(os.getenv("TEST_PORT", "8008"))

#: 개발 서버가 이미 떠 있으면 HTTP 는 그 서버의 DB 로 간다. 그때 in-process engine 만
#: 임시 DB 로 돌리면 한 테스트가 두 DB 를 보게 되므로 손대지 않는다.
USING_RUNNING_DEV_SERVER = _server_already_running(TEST_PORT)


def _needs_temp_db(url) -> bool:
    if not url:
        return True
    #: 셸에 개발 DB 가 박혀 있으면 그대로 쓰지 않는다. 되돌릴 수 없는 쓰기가 들어간다.
    #: 일부러 쓰려면 test_run_tc_sync.py 와 같은 이름의 opt-in 을 준다.
    return url.endswith(DEV_DB_SUFFIX) and os.getenv("ALLOW_DEV_DB") != "1"


def _isolate_database_url():
    if USING_RUNNING_DEV_SERVER or not _needs_temp_db(os.getenv("DATABASE_URL")):
        return None
    tmp_dir = tempfile.mkdtemp(prefix="ymtc-test-db-")
    path = os.path.join(tmp_dir, "ymtc_test.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = f"sqlite:///{path}"
    #: ignore_errors 를 켠다. Windows 에서 SQLite 핸들이 아직 열려 있으면 삭제가
    #: 실패하는데, 임시 폴더가 남는 것은 테스트 결과를 바꾸지 않는다.
    atexit.register(shutil.rmtree, tmp_dir, True)
    return tmp_dir


TEST_DB_DIR = _isolate_database_url()


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
        _seed_admin(base_url, admin_pw)
        yield
        return

    # 임시 DB 는 이 파일 맨 위에서 이미 DATABASE_URL 에 박아 두었다.
    # 여기서 다시 바꾸면 수집 단계에 만들어진 engine 과 갈라진다.
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
