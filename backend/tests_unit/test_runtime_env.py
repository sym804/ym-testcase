"""서버리스(Vercel) 기본값과 설정 검사.

하위 프로세스로 앱을 임포트해 본다. 환경변수와 모듈 전역 상태가 테스트끼리 섞이지 않게.
"""
import os
import subprocess
import sys

import testing_db

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_DB = "postgresql+psycopg2://u:p@127.0.0.1:1/x"


def _run(code: str, **env_over) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in ("VERCEL", "STORAGE_BACKEND", "TRUSTED_PROXY_HEADER", "DB_POOL",
                        "RUN_MIGRATIONS_ON_STARTUP", "RUN_MAINTENANCE_ON_STARTUP")}
    env.update({"DATABASE_URL": FAKE_DB, "DATABASE_URL_DIRECT": "", "SECRET_KEY": "k" * 32,
                "ENV_FILE": os.path.join(BACKEND, "does-not-exist.env")})
    env.update(env_over)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


SUPA = {"STORAGE_BACKEND": "supabase", "SUPABASE_URL": "https://x.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "k", "STORAGE_BUCKET": "b"}


def test_서버리스에서_로컬_저장소면_기동하지_않는다():
    r = _run("import main", VERCEL="1")
    assert r.returncode != 0
    assert "STORAGE_BACKEND" in r.stderr


def test_서버리스에서_신뢰_헤더가_없으면_경고한다():
    r = _run("import main", VERCEL="1", **SUPA)
    assert r.returncode == 0, r.stderr
    assert "TRUSTED_PROXY_HEADER" in r.stderr


def test_서버리스_기본값():
    code = ("import database, services.runtime_env as e;"
            "print(type(database.engine.pool).__name__,"
            " e.env_flag('RUN_MIGRATIONS_ON_STARTUP'), e.env_flag('RUN_MAINTENANCE_ON_STARTUP'))")
    r = _run(code, VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", **SUPA)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["NullPool", "False", "False"]


def test_로컬_기본값():
    code = ("import database, services.runtime_env as e;"
            "print(type(database.engine.pool).__name__,"
            " e.env_flag('RUN_MIGRATIONS_ON_STARTUP'), e.env_flag('RUN_MAINTENANCE_ON_STARTUP'))")
    r = _run(code)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["QueuePool", "True", "True"]


def test_lifespan_없이도_옛_스키마면_503():
    """Vercel 이 ASGI lifespan 을 부르지 않아도 첫 요청에서 판정한다."""
    url = testing_db.create_database(prefix="ymtc_rt")
    code = (
        "from fastapi.testclient import TestClient\n"
        "from main import app\n"
        "c = TestClient(app)\n"
        "print(c.get('/api/projects').status_code, c.get('/api/config').status_code)\n"
    )
    try:
        r = _run(code, VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", DATABASE_URL=url, **SUPA)
    finally:
        testing_db.drop_database(url)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[-2:] == ["503", "200"]
