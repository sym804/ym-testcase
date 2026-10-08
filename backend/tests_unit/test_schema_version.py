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


def test_코드가_모르는_새_리비전은_막지_않는다(conn):
    """롤백(이전 배포 승격)은 새 스키마 위에서 옛 코드를 띄운다. 그때 기동을 막으면 안 된다."""
    conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) primary key)"))
    conn.execute(text("INSERT INTO alembic_version VALUES ('0099_future')"))
    assert_known_revision(conn, _script_dir())


# ── 서버리스 기동: 스키마가 코드보다 옛것이면 503 ───────────────────────────────

from services.schema_version import schema_status  # noqa: E402


def _set_rev(conn, rev):
    conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) primary key)"))
    conn.execute(text("INSERT INTO alembic_version VALUES (:r)"), {"r": rev})


def test_빈_DB_는_미초기화(conn):
    assert schema_status(conn, _script_dir()) == "empty"


def test_head_면_current(conn):
    _set_rev(conn, _script_dir().get_current_head())
    assert schema_status(conn, _script_dir()) == "current"


def test_옛_리비전이면_behind(conn):
    _set_rev(conn, "0001_pg_baseline")
    assert schema_status(conn, _script_dir()) == "behind"


def test_모르는_새_리비전이면_ahead(conn):
    _set_rev(conn, "0099_future")
    assert schema_status(conn, _script_dir()) == "ahead"


def test_스키마가_뒤처지면_API_는_503_헬스와_설정은_통과(monkeypatch):
    from fastapi.testclient import TestClient
    from main import app

    client = TestClient(app)
    app.state.schema_behind = True
    try:
        r = client.get("/api/projects")
        assert r.status_code == 503
        assert "마이그레이션" in r.json()["detail"]
        assert client.get("/").status_code == 200
        assert client.get("/api/config").status_code == 200
    finally:
        app.state.schema_behind = False


def test_마이그레이션을_끈_기동에서_빈_DB_면_API_가_503():
    import subprocess
    import sys

    url = testing_db.create_database(prefix="ymtc_sv_boot")
    code = (
        "from fastapi.testclient import TestClient\n"
        "from main import app\n"
        "with TestClient(app) as c:\n"
        "    print(c.get('/api/projects').status_code, c.get('/').status_code)\n"
    )
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="", RUN_MIGRATIONS_ON_STARTUP="0",
               RUN_MAINTENANCE_ON_STARTUP="0")
    try:
        r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    finally:
        testing_db.drop_database(url)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[-2:] == ["503", "200"]
