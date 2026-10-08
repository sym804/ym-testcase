"""pytest 는 어떤 경우에도 세션 전용 임시 PostgreSQL DB 를 쓴다.

SQLite 시절에는 주소가 `/tc_manager.db` 로 끝날 때만 격리했다. PostgreSQL 주소는
그 판정에 안 걸려 그대로 쓰였고, `.env` 에 운영 주소가 있으면 테스트가 거기 썼다.

★`import conftest` 로 값을 읽지 않는다. tests_unit/conftest.py 가 같은 이름을 가로챈다.
  conftest 가 dev_db_guard 에 적어 둔 값을 읽는다.
"""
import os
import subprocess
import sys

import pytest

import dev_db_guard

BACKEND = os.path.dirname(os.path.abspath(__file__))


def _skip_if_running_server():
    if dev_db_guard.USING_RUNNING_DEV_SERVER:
        pytest.skip("이미 떠 있는 서버를 쓰는 모드")


def test_세션_DB_는_임시_DB_다():
    from sqlalchemy.engine import make_url

    _skip_if_running_server()
    name = make_url(os.environ["DATABASE_URL"]).database
    assert name.startswith("ymtc_test_"), name


def test_앱_엔진도_같은_임시_DB_를_본다():
    from database import engine

    _skip_if_running_server()
    assert engine.url.database == dev_db_guard.SESSION_DATABASE_NAME


def test_셸의_원격_DATABASE_URL_은_무시하고_임시_DB_를_쓴다():
    """셸에 운영 Supabase 주소가 있어도 pytest 는 그 주소를 쓰지 않는다."""
    code = (
        "import conftest, os;"
        "from sqlalchemy.engine import make_url;"
        "u = make_url(os.environ['DATABASE_URL']);"
        "print(u.host, u.database)"
    )
    env = dict(os.environ,
               DATABASE_URL="postgresql+psycopg2://u:p@db.example.supabase.co:5432/postgres",
               TEST_PORT="18999", TEST_BASE_URL="http://127.0.0.1:18999")
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    host, db = r.stdout.split()
    assert host in ("127.0.0.1", "localhost"), host
    assert db.startswith("ymtc_test_"), db


def test_env_파일의_원격_직결_주소는_테스트_마이그레이션에_쓰이지_않는다(tmp_path):
    """`.env` 에 운영 직결 주소가 있어도 테스트 세션의 마이그레이션은 임시 DB 로 간다.

    pop 만 하면 하위 프로세스의 dotenv 로딩이 `.env` 값을 다시 채운다(2026-10-08 재현).
    """
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL_DIRECT=postgresql+psycopg2://evil:evil@203.0.113.9:5432/prod?connect_timeout=2\n",
        encoding="utf-8",
    )
    code = "import conftest, os; print(repr(os.environ.get('DATABASE_URL_DIRECT')))"
    env = dict(os.environ, ENV_FILE=str(env_file), TEST_PORT="18998", TEST_BASE_URL="http://127.0.0.1:18998")
    env.pop("DATABASE_URL_DIRECT", None)
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    assert r.returncode == 0, r.stderr
    assert "203.0.113.9" not in r.stdout + r.stderr
    assert r.stdout.strip() == "''"


def test_이미_떠_있는_서버가_있으면_DATABASE_URL_을_건드리지_않는다():
    """HTTP 는 그 서버의 DB 로 가는데 in-process engine 만 임시 DB 로 돌리면 한 테스트가
    두 DB 를 본다. 이 모드에서는 임시 DB 를 만들지 않고 주소를 그대로 둔다."""
    import http.server
    import socketserver
    import threading

    given = "postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc_running"
    code = (
        "import conftest, os, dev_db_guard;"
        "print(os.environ['DATABASE_URL']);"
        "print(dev_db_guard.SESSION_DATABASE_NAME)"
    )
    with socketserver.TCPServer(("127.0.0.1", 0), http.server.SimpleHTTPRequestHandler) as srv:
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            env = dict(os.environ, DATABASE_URL=given, TEST_PORT=str(port),
                       TEST_BASE_URL=f"http://127.0.0.1:{port}")
            r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        finally:
            srv.shutdown()
    assert r.returncode == 0, r.stderr
    url, name = r.stdout.split()
    assert url == given
    assert name == "None"
