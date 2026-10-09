"""단위 테스트 전용 설정.

backend/conftest.py 의 `_server` 픽스처는 8008 포트에 서버가 이미 떠 있으면
그 서버를 그대로 쓰고 admin 계정을 시드한다. 즉 개발 서버를 켠 채로 pytest 를
돌리면 실 DB 에 쓰기가 들어간다.

이 디렉터리의 테스트는 서버가 필요 없다. 같은 이름으로 다시 정의해 그 픽스처를
무력화한다(가까운 conftest 가 이긴다). 여기 테스트는 각자 임시 DB 만 쓴다.
"""
import socket
import threading
import time
from types import SimpleNamespace

import pytest
import uvicorn
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="session", autouse=True)
def _server():
    yield

_AUTH_ENV_KEYS = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "AUTH_COMPANY_DOMAINS",
                  "AUTH_ALLOW_PERSONAL", "AUTH_APPROVAL", "BOOTSTRAP_TOKEN", "REGISTER_MAX_PER_HOUR")


@pytest.fixture(scope="module")
def live_app():
    """앱을 빈 포트에 띄운다(lifespan 끔). DB 는 auth_env 가 get_db 를 갈아 끼운다."""
    from main import app

    # schema_guard 가 database.engine(테스트 밖 주소일 수 있다)에 접속하지 않게 한다.
    app.state.schema_behind = False
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="off", log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    deadline = time.time() + 15
    while not srv.started and time.time() < deadline:
        time.sleep(0.05)
    assert srv.started, "테스트 서버가 뜨지 않았다"
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    th.join(timeout=10)


@pytest.fixture
def auth_env(pg_engine, live_app, monkeypatch):
    """임시 스키마 DB + 인증 환경변수 초기화. 테스트가 monkeypatch.setenv 로 정책을 바꾼다."""
    from database import get_db
    from main import app
    from services import rate_limit

    Session = sessionmaker(bind=pg_engine)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    for key in _AUTH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENV", "development")
    app.dependency_overrides[get_db] = _db
    rate_limit.clear_all(engine=pg_engine)
    yield SimpleNamespace(base=live_app, Session=Session, engine=pg_engine)
    app.dependency_overrides.clear()
