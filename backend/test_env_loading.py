"""backend/.env 로딩 회귀 테스트

과거 사고: README 3단계대로 backend/.env 에 SECRET_KEY 를 넣어도
어디에서도 .env 를 읽지 않아 매 기동마다 랜덤 키가 생성됐다.
그 결과 서버를 재시작할 때마다 모든 로그인 세션이 끊겼다.
"""
import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def _run(env_file, code):
    env = dict(os.environ)
    env["ENV_FILE"] = str(env_file)
    for key in ("SECRET_KEY", "TOKEN_EXPIRE_HOURS", "CORS_ORIGINS", "ENV", "DATABASE_URL"):
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


def test_env_file_supplies_secret_key(tmp_path):
    """.env 에 적힌 SECRET_KEY 가 auth 모듈에 실제로 반영된다"""
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=env-file-secret-123\n", encoding="utf-8")

    r = _run(env_file, "import auth; print(auth.SECRET_KEY)")

    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "env-file-secret-123"


def test_env_file_supplies_token_expire_hours(tmp_path):
    """SECRET_KEY 외 다른 설정도 .env 에서 읽힌다"""
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=x\nTOKEN_EXPIRE_HOURS=5\n", encoding="utf-8")

    r = _run(env_file, "import auth; print(auth.ACCESS_TOKEN_EXPIRE_HOURS)")

    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "5"


def test_real_env_var_wins_over_env_file(tmp_path):
    """이미 설정된 환경변수를 .env 가 덮어쓰지 않는다 (테스트 격리 보호)"""
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=from-file\n", encoding="utf-8")

    env = dict(os.environ)
    env["ENV_FILE"] = str(env_file)
    env["SECRET_KEY"] = "from-real-env"
    r = subprocess.run(
        [sys.executable, "-c", "import auth; print(auth.SECRET_KEY)"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )

    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "from-real-env"


def test_database_url_env_var_not_clobbered_by_env_file(tmp_path):
    """conftest 가 미리 지정한 DATABASE_URL 을 .env 가 덮어쓰지 않는다"""
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite:///./from_file.db\n", encoding="utf-8")

    env = dict(os.environ)
    env["ENV_FILE"] = str(env_file)
    env["DATABASE_URL"] = "sqlite:///./from_real_env.db"
    r = subprocess.run(
        [sys.executable, "-c", "import database; print(database.DATABASE_URL)"],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )

    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "sqlite:///./from_real_env.db"


def test_env_file_supplies_cors_origins_via_main(tmp_path):
    """main 모듈이 읽는 설정도 .env 에서 온다 (auth/database 외 진입점 커버)"""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SECRET_KEY=x\nCORS_ORIGINS=http://example.test:1234\n", encoding="utf-8"
    )

    r = _run(env_file, "import main; print(','.join(main.cors_origins))")

    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "http://example.test:1234"
