"""QA 2인(계획 4b) 지적의 재현 테스트. 고치기 전 코드에서 실패해야 한다."""
import pytest
import requests
from fastapi import HTTPException
from sqlalchemy import text

from auth import verify_password
from auth_helpers import PW, bearer, login, make_user
from models import User, UserRole, UserStatus
from services.locks import LockNs


def _change(ra, s, uid):
    from schemas import PasswordChange
    me = s.get(User, uid)
    return ra.change_password(PasswordChange(current_password=PW, new_password="NewPassw0rd!"), db=s, current_user=me)


def test_잠금을_기다리는_사이_중지되면_비밀번호를_바꾸지_않는다(auth_env, monkeypatch):
    import routes.auth as ra

    uid = make_user(auth_env.Session, username="u")
    real = ra.lock_accounts

    def disable_then_lock(db):
        with auth_env.Session() as s2:
            u = s2.get(User, uid)
            u.status = UserStatus.disabled
            u.token_version = (u.token_version or 0) + 1
            s2.commit()
        real(db)

    monkeypatch.setattr(ra, "lock_accounts", disable_then_lock)
    with auth_env.Session() as s, pytest.raises(HTTPException) as e:
        _change(ra, s, uid)
    assert e.value.status_code == 401
    with auth_env.Session() as s:
        assert verify_password(PW, s.get(User, uid).password_hash)


def test_잠금을_기다리는_사이_비밀번호가_바뀌면_409(auth_env, monkeypatch):
    import routes.auth as ra
    from auth import hash_password

    uid = make_user(auth_env.Session, username="u")
    real = ra.lock_accounts

    def change_then_lock(db):
        with auth_env.Session() as s2:
            s2.get(User, uid).password_hash = hash_password("Other-Passw0rd!")
            s2.commit()
        real(db)

    monkeypatch.setattr(ra, "lock_accounts", change_then_lock)
    with auth_env.Session() as s, pytest.raises(HTTPException) as e:
        _change(ra, s, uid)
    assert e.value.status_code == 409
    with auth_env.Session() as s:
        assert verify_password("Other-Passw0rd!", s.get(User, uid).password_hash)


def test_잠금을_기다리는_사이_중지되면_Google_연결을_풀지_않는다(auth_env, monkeypatch):
    import routes.google_auth as rga

    uid = make_user(auth_env.Session, username="u", google_sub="sub-1")
    real = rga.lock_accounts

    def disable_then_lock(db):
        with auth_env.Session() as s2:
            u = s2.get(User, uid)
            u.status = UserStatus.disabled
            u.token_version = (u.token_version or 0) + 1
            s2.commit()
        real(db)

    monkeypatch.setattr(rga, "lock_accounts", disable_then_lock)
    with auth_env.Session() as s, pytest.raises(HTTPException) as e:
        rga.google_unlink(db=s, current_user=s.get(User, uid))
    assert e.value.status_code == 401
    with auth_env.Session() as s:
        assert s.get(User, uid).google_sub == "sub-1"


def test_비밀번호_찾기_실패는_계정_잠금을_기다리지_않는다(auth_env, monkeypatch):
    """로그인 없이 부르는 API 가 전역 계정 잠금 안에서 bcrypt 를 돌리면 다른 계정 작업이 줄을 선다."""
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "300")
    holder = auth_env.Session()
    try:
        holder.execute(text("SELECT pg_advisory_xact_lock(:ns, 0)"), {"ns": int(LockNs.ACCOUNTS)})
        r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                          json={"username": "nobody@example.com", "code": "x" * 12, "new_password": "NewPassw0rd!"})
        assert r.status_code == 401, r.text
    finally:
        holder.rollback()
        holder.close()


def test_자기_자신의_이메일은_해제하지_못한다(auth_env):
    uid = make_user(auth_env.Session, username="boss@x.com", email="boss@x.com", role=UserRole.admin)
    h = bearer(login(auth_env.base, "boss@x.com"))
    r = requests.post(auth_env.base + f"/api/auth/users/{uid}/release-email", headers=h)
    assert r.status_code == 409
