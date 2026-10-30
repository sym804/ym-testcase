"""서버리스(Vercel) 기본값과 설정 검사.

하위 프로세스로 앱을 임포트해 본다. 환경변수와 모듈 전역 상태가 테스트끼리 섞이지 않게.
"""
import os
import subprocess
import sys

import pytest

import testing_db

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAKE_DB = "postgresql+psycopg2://u:p@127.0.0.1:1/x"


def _run(code: str, **env_over) -> subprocess.CompletedProcess:
    # ★GOOGLE_*, AUTH_* 도 뺀다. 앞선 테스트가 .env 를 읽어 GOOGLE_CLIENT_ID 를 올려 두면 ENV=production
    #   기동이 GOOGLE_REDIRECT_URI 필수 검사에 걸려 전체 실행에서만 실패한다(실측).
    env = {k: v for k, v in os.environ.items()
           if k not in ("VERCEL", "STORAGE_BACKEND", "TRUSTED_PROXY_HEADER", "DB_POOL", "ENV",
                        "RUN_MIGRATIONS_ON_STARTUP", "RUN_MAINTENANCE_ON_STARTUP")
           and not k.startswith(("GOOGLE_", "AUTH_"))}
    env.update({"DATABASE_URL": FAKE_DB, "DATABASE_URL_DIRECT": "", "SECRET_KEY": "k" * 32,
                "ENV_FILE": os.path.join(BACKEND, "does-not-exist.env")})
    env.update(env_over)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


SUPA = {"STORAGE_BACKEND": "supabase", "SUPABASE_URL": "https://x.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "k", "STORAGE_BUCKET": "b"}
#: 서버리스에서 기동에 필요한 운영 설정(SYM-206)
PROD = {"ENV": "production", "AUTH_APPROVAL": "all"}


def test_서버리스에서_로컬_저장소면_기동하지_않는다():
    r = _run("import main", VERCEL="1")
    assert r.returncode != 0
    assert "STORAGE_BACKEND" in r.stderr


@pytest.mark.parametrize("drop", ["ENV", "SECRET_KEY", "AUTH_APPROVAL"])
def test_서버리스에서_운영_설정이_빠지면_기동하지_않는다(drop):
    """ENV 가 빠지면 첫 관리자 토큰 검사, Secure 쿠키, SECRET_KEY 필수 검사가 함께 꺼진다(SYM-206)."""
    r = _run("import main", VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", **SUPA, **{**PROD, drop: ""})
    assert r.returncode != 0
    assert drop in r.stderr


def test_서버리스에서_SECRET_KEY_가_공백뿐이면_기동하지_않는다():
    """auth.py 는 빈 문자열만 막는다. 공백만 있는 키는 이 검사가 혼자 잡는다."""
    r = _run("import main", VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", **SUPA, **{**PROD, "SECRET_KEY": "   "})
    assert r.returncode != 0
    assert "SECRET_KEY 를 지정해야 한다" in r.stderr


def test_서버리스에서_ENV_가_production_이_아니면_기동하지_않는다():
    r = _run("import main", VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", **SUPA, **{**PROD, "ENV": "development"})
    assert r.returncode != 0
    assert "ENV=production" in r.stderr


def test_로컬은_운영_설정_없이도_뜬다():
    r = _run("import main", ENV="", AUTH_APPROVAL="")
    assert r.returncode == 0, r.stderr


def test_서버리스에서_신뢰_헤더가_없으면_경고한다():
    r = _run("import main", VERCEL="1", **SUPA, **PROD)
    assert r.returncode == 0, r.stderr
    assert "TRUSTED_PROXY_HEADER" in r.stderr


def test_서버리스_기본값():
    code = ("import database, services.runtime_env as e;"
            "print(type(database.engine.pool).__name__,"
            " e.env_flag('RUN_MIGRATIONS_ON_STARTUP'), e.env_flag('RUN_MAINTENANCE_ON_STARTUP'))")
    r = _run(code, VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", **SUPA, **PROD)
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
        "from asgi_testing import asgi_get\n"
        "from main import app\n"
        "print(asgi_get(app, '/api/projects')[0], asgi_get(app, '/api/config')[0])\n"
    )
    try:
        r = _run(code, VERCEL="1", TRUSTED_PROXY_HEADER="x-real-ip", DATABASE_URL=url, **SUPA, **PROD)
    finally:
        testing_db.drop_database(url)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[-2:] == ["503", "200"]
