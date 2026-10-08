"""DB 주소는 반드시 명시한다. 조용히 SQLite 로 떨어지면 배포가 엉뚱한 파일에 성공한다."""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_database(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env.update(env_overrides)
    env["ENV_FILE"] = os.path.join(BACKEND, "does-not-exist.env")
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
