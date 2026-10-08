"""모르는 리비전을 만나면 sqlite-legacy 이력이라고 알리고 멈춘다."""
import os
import sys

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db
from services.schema_version import assert_known_revision


def _script_dir():
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    return ScriptDirectory.from_config(cfg)


@pytest.fixture
def conn():
    url = testing_db.create_database(prefix="ymtc_sv")
    eng = create_engine(url)
    with eng.connect() as c:
        yield c
    eng.dispose()
    testing_db.drop_database(url)


def test_빈_DB_는_통과한다(conn):
    assert_known_revision(conn, _script_dir())


def test_옛_SQLite_이력의_리비전이면_안내하고_멈춘다(conn):
    conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) primary key)"))
    conn.execute(text("INSERT INTO alembic_version VALUES ('5e0b8c2d4f17')"))
    with pytest.raises(RuntimeError, match="sqlite-legacy"):
        assert_known_revision(conn, _script_dir())


def test_현재_head_면_통과한다(conn):
    head = _script_dir().get_current_head()
    conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) primary key)"))
    conn.execute(text("INSERT INTO alembic_version VALUES (:h)"), {"h": head})
    assert_known_revision(conn, _script_dir())
