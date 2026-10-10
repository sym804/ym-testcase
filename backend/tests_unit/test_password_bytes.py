"""bcrypt 72바이트 상한

bcrypt 5.0 은 72바이트를 넘는 비밀번호에 hashpw · checkpw 모두 ValueError 를 낸다. 예전에는
그대로 500 이 됐다. 한글은 한 글자가 3바이트라 25자면 넘는다.

- 로그인 · 코드 확인: 틀린 비밀번호와 같은 401(실패 횟수도 기록).
- 가입 · 비밀번호 변경 · 코드로 새 비밀번호: 400 과 바이트 상한 안내.

실행: cd backend && python -m pytest tests_unit/test_password_bytes.py -q
"""
import pytest
import requests

from auth_helpers import PW, bearer, login, make_user
from models import RateLimitEvent, UserRole

LONG_ASCII = "a" * 73
LONG_KO = "가" * 25  # 75바이트


def _login_failures(env):
    s = env.Session()
    try:
        return s.query(RateLimitEvent).filter(RateLimitEvent.bucket == "login").count()
    finally:
        s.close()


@pytest.mark.parametrize("pw", [LONG_ASCII, LONG_KO], ids=["ascii73", "ko25"])
@pytest.mark.parametrize("who", ["있는_계정", "없는_계정"])
def test_로그인의_긴_비밀번호는_401_이고_실패로_센다(auth_env, pw, who):
    make_user(auth_env.Session, username="u1")
    before = _login_failures(auth_env)
    r = login(auth_env.base, "u1" if who == "있는_계정" else "ghost", pw)
    assert r.status_code == 401, r.text
    assert r.json()["detail"] == "아이디 또는 비밀번호가 올바르지 않습니다."
    assert _login_failures(auth_env) == before + 1


@pytest.mark.parametrize("pw", [LONG_ASCII, LONG_KO], ids=["ascii73", "ko25"])
def test_가입의_긴_비밀번호는_400(auth_env, pw):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    r = requests.post(auth_env.base + "/api/auth/register",
                      json={"email": "n@example.com", "password": pw, "display_name": "N"})
    assert r.status_code == 400, r.text
    assert "72" in r.json()["detail"]


def test_첫_관리자_가입의_긴_비밀번호도_400(auth_env):
    r = requests.post(auth_env.base + "/api/auth/register",
                      json={"username": "boss", "password": LONG_KO, "display_name": "N"})
    assert r.status_code == 400, r.text


def test_비밀번호_변경의_긴_새_비밀번호는_400(auth_env):
    make_user(auth_env.Session, username="u1")
    h = bearer(login(auth_env.base, "u1"))
    r = requests.put(auth_env.base + "/api/auth/change-password",
                     json={"current_password": PW, "new_password": LONG_KO}, headers=h)
    assert r.status_code == 400, r.text
    assert "72" in r.json()["detail"]


def test_비밀번호_변경의_긴_현재_비밀번호는_틀린_것과_같다(auth_env):
    make_user(auth_env.Session, username="u1")
    h = bearer(login(auth_env.base, "u1"))
    r = requests.put(auth_env.base + "/api/auth/change-password",
                     json={"current_password": LONG_ASCII, "new_password": "Another1!pw"}, headers=h)
    assert (r.status_code, r.json()["detail"]) == (400, "현재 비밀번호가 올바르지 않습니다."), r.text


def test_코드로_초기화의_긴_코드는_401(auth_env):
    make_user(auth_env.Session, username="u1")
    r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                      json={"username": "u1", "code": LONG_ASCII, "new_password": "Another1!pw"})
    assert r.status_code == 401, r.text


def test_코드로_초기화의_긴_새_비밀번호는_400(auth_env):
    make_user(auth_env.Session, username="u1")
    r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                      json={"username": "u1", "code": "123456", "new_password": LONG_KO})
    assert r.status_code == 400, r.text
    assert "72" in r.json()["detail"]


def test_72바이트_딱_맞으면_가입과_로그인이_된다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    pw = "가" * 24  # 72바이트
    r = requests.post(auth_env.base + "/api/auth/register",
                      json={"email": "n@example.com", "password": pw, "display_name": "N"})
    assert r.status_code == 201, r.text
    assert login(auth_env.base, "n@example.com", pw).status_code == 200
