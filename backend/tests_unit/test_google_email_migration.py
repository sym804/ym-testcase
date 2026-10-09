"""0008: 연결된 Google 계정의 이메일 칸. 기존 연결은 비어 있다가 다음 Google 로그인 때 채워진다."""
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
    u = testing_db.create_database(prefix="ymtc_0008")
    yield u
    testing_db.drop_database(u)


def test_기존_연결은_빈_칸으로_올라가고_내렸다_올려도_된다(url):
    _alembic(url, "upgrade", "0007_account_identity")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, "
                       "token_version, google_sub) VALUES ('linked', 'h', 'L', 'admin', false, 0, 'sub-1')"))
    _alembic(url, "upgrade", "head")
    with eng.begin() as c:
        assert c.execute(text("SELECT google_sub, google_email FROM users WHERE username='linked'")).one() == (
            "sub-1", None)
        c.execute(text("UPDATE users SET google_email='l@gmail.com' WHERE username='linked'"))
    _alembic(url, "downgrade", "0007_account_identity")
    _alembic(url, "upgrade", "head")
    with eng.begin() as c:
        assert c.execute(text("SELECT google_email FROM users WHERE username='linked'")).scalar() is None
    eng.dispose()
