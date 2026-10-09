"""0007: 기존 사용자는 active, 비밀번호 칸은 비어도 됨, 복구 이력은 사용자 삭제를 막지 않는다."""
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
    u = testing_db.create_database(prefix="ymtc_0007")
    yield u
    testing_db.drop_database(u)


def test_기존_행이_active_로_채워지고_새_칸이_생긴다(url):
    _alembic(url, "upgrade", "0006_storage_deletions")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, token_version) "
                       "VALUES ('old', 'h', 'Old', 'admin', false, 0)"))
    _alembic(url, "upgrade", "head")
    with eng.begin() as c:
        row = c.execute(text("SELECT status::text, email, email_verified, google_sub FROM users WHERE username='old'")).one()
        assert tuple(row) == ("active", None, False, None)
        c.execute(text("INSERT INTO users (username, display_name, role, must_change_password, token_version) "
                       "VALUES ('google-only', 'G', 'user', false, 0)"))
    eng.dispose()


def test_복구_이력이_있어도_사용자를_지울_수_있다(url):
    _alembic(url, "upgrade", "head")
    eng = create_engine(url)
    with eng.begin() as c:
        uid = c.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, token_version) "
                             "VALUES ('p', 'h', 'P', 'user', false, 0) RETURNING id")).scalar()
        c.execute(text("INSERT INTO account_requests (request_type, status, contact, user_id, resolved_by_id) "
                       "VALUES ('reset_password', 'approved', 'x', :u, :u)"), {"u": uid})
        c.execute(text("DELETE FROM users WHERE id = :u"), {"u": uid})
        assert tuple(c.execute(text("SELECT user_id, resolved_by_id FROM account_requests")).one()) == (None, None)
    eng.dispose()


def test_내렸다_올려도_된다(url):
    _alembic(url, "upgrade", "head")
    _alembic(url, "downgrade", "0006_storage_deletions")
    _alembic(url, "upgrade", "head")
