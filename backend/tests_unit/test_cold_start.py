"""서버리스 콜드 스타트에 무거운 임포트와 계산을 싣지 않는다(SYM 이슈: 첫 접속 지연).

새 인스턴스는 앱 임포트와 첫 요청의 스키마 판정을 사용자 요청 안에서 치른다.
openpyxl(엑셀), alembic(마이그레이션), bcrypt 더미 해시가 여기에 실려 있었다.
하위 프로세스로 앱을 띄워 sys.modules 와 계산 여부를 본다. 누가 최상단 임포트를
되살리면 이 테스트가 실패한다.
"""
import os
import subprocess
import sys

import testing_db

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run(code: str, database_url: str, **env_over) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items()
           if k not in ("VERCEL", "STORAGE_BACKEND", "RUN_MIGRATIONS_ON_STARTUP", "RUN_MAINTENANCE_ON_STARTUP")}
    env.update({"DATABASE_URL": database_url, "DATABASE_URL_DIRECT": "", "SECRET_KEY": "k" * 32,
                "ENV_FILE": os.path.join(BACKEND, "does-not-exist.env")})
    env.update(env_over)
    return subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)


def test_앱_임포트는_openpyxl_alembic_을_올리지_않고_bcrypt_해시를_만들지_않는다():
    code = (
        "import bcrypt\n"
        "calls = []\n"
        "_orig = bcrypt.hashpw\n"
        "bcrypt.hashpw = lambda *a, **k: (calls.append(1), _orig(*a, **k))[1]\n"
        "import sys, main\n"
        "print('openpyxl' in sys.modules, 'alembic' in sys.modules, len(calls))\n"
    )
    r = _run(code, "postgresql+psycopg2://u:p@127.0.0.1:1/x")
    assert r.returncode == 0, r.stderr
    assert r.stdout.split()[-3:] == ["False", "False", "0"]


def test_더미_해시는_실제_해시와_비용이_같다():
    """비용(rounds)이 다르면 계정이 없을 때와 있을 때 대조 시간이 달라져 계정 유무가 샌다."""
    import bcrypt
    import auth

    dummy = auth._dummy_hash()
    assert dummy.split("$")[2] == auth.hash_password("x").split("$")[2]
    assert bcrypt.checkpw(b"anything", dummy.encode()) is False


def test_첫_요청의_스키마_판정은_alembic_을_올리지_않는다():
    url = testing_db.create_database(prefix="ymtc_cold")
    code = (
        "import sys\n"
        "from asgi_testing import asgi_get\n"
        "import main\n"
        "status, _ = asgi_get(main.app, '/api/config')\n"
        "print(status, main.app.state.schema_behind, 'alembic' in sys.modules)\n"
    )
    try:
        # 마이그레이션을 끈 기동(서버리스 경로)이어야 미들웨어가 판정한다
        r = _run(code, url, RUN_MIGRATIONS_ON_STARTUP="0")
    finally:
        testing_db.drop_database(url)
    assert r.returncode == 0, r.stderr
    # 빈 DB 라 뒤처짐(True)으로 판정해야 한다. 판정은 하되 alembic 없이.
    assert r.stdout.split()[-3:] == ["200", "True", "False"]
