"""DB 주소는 반드시 명시한다. 조용히 SQLite 로 떨어지면 배포가 엉뚱한 파일에 성공한다."""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_database(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env.update(env_overrides)
    env["ENV_FILE"] = os.path.join(BACKEND, "does-not-exist.env")
    # 아래에서 UTF-8 로 읽는다. 자식도 UTF-8 로 쓰게 한다(Windows 기본은 cp949 라 한글 오류가 깨진다)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-c", "import database"],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_DATABASE_URL_이_없으면_임포트에서_실패한다():
    r = _import_database({})
    assert r.returncode != 0
    assert "DATABASE_URL" in r.stderr


def test_sqlite_주소는_거부한다():
    r = _import_database({"DATABASE_URL": "sqlite:///./x.db"})
    assert r.returncode != 0
    assert "PostgreSQL" in r.stderr


def test_postgresql_주소면_임포트된다():
    r = _import_database({"DATABASE_URL": "postgresql+psycopg2://u:p@127.0.0.1:1/x"})
    assert r.returncode == 0, r.stderr


def test_alembic_ini_에_기본_주소가_없다():
    ini = open(os.path.join(BACKEND, "alembic.ini"), encoding="utf-8").read()
    assert "sqlite" not in ini


def _alembic(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "DATABASE_URL_DIRECT")}
    env.update(env_overrides)
    env["ENV_FILE"] = os.path.join(BACKEND, "does-not-exist.env")
    # 아래에서 UTF-8 로 읽는다. 자식도 UTF-8 로 쓰게 한다(Windows 기본은 cp949 라 한글 오류가 깨진다)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )


def test_직결_주소만_있어도_alembic_이_돈다():
    import testing_db
    url = testing_db.create_database(prefix="ymtc_directonly")
    try:
        r = _alembic({"DATABASE_URL_DIRECT": url})
        assert r.returncode == 0, r.stderr
    finally:
        testing_db.drop_database(url)


def test_앱은_로컬인데_직결_주소만_원격이면_멈춘다():
    r = _alembic({
        "DATABASE_URL": "postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc",
        "DATABASE_URL_DIRECT": "postgresql+psycopg2://u:p@db.example.supabase.co:5432/postgres",
    })
    assert r.returncode != 0
    assert "원격" in r.stderr
