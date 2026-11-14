"""0010: API 키 범위 칸. 이미 발급한 키는 전체 범위로 올라가고, 내렸다 올려도 된다(SYM-217)."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db


def _alembic(url, *args):
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="")
    r = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr


@pytest.fixture
def url():
    u = testing_db.create_database(prefix="ymtc_0010")
    yield u
    testing_db.drop_database(u)


def test_기존_키는_전체_범위로_올라간다(url):
    _alembic(url, "upgrade", "0009_result_tc_snapshot")
    eng = create_engine(url)
    with eng.begin() as c:
        uid = c.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, "
                             "token_version) VALUES ('ci', 'h', 'C', 'user', false, 0) RETURNING id")).scalar()
        c.execute(text("INSERT INTO api_keys (user_id, name, key_id, key_hash) VALUES (:u, 'old', 'old00001', :h)"),
                  {"u": uid, "h": "0" * 64})
    _alembic(url, "upgrade", "head")
    with eng.begin() as c:
        assert c.execute(text("SELECT scope FROM api_keys WHERE key_id = 'old00001'")).scalar() == "full"
    _alembic(url, "downgrade", "0009_result_tc_snapshot")
    _alembic(url, "upgrade", "head")
    with eng.begin() as c:
        assert c.execute(text("SELECT scope FROM api_keys WHERE key_id = 'old00001'")).scalar() == "full"
    eng.dispose()
