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
