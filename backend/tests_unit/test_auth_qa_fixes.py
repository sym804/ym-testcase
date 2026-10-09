"""QA 2인(계획 4a) 지적의 재현 테스트. 각 테스트는 고치기 전 코드에서 실패해야 한다."""
import threading
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from fastapi import HTTPException
from starlette.requests import Request

from auth import hash_password
from auth_helpers import PW, bearer, login, make_user
from models import AccountRequest, AccountRequestStatus, AccountRequestType, User, UserRole, UserStatus, now_kst
from services import google_oauth as g


def _req(ip="127.0.0.1"):
    return Request({"type": "http", "method": "POST", "path": "/api/auth/register", "headers": [],
                    "client": (ip, 0), "query_string": b""})


def _reg(base, **body):
    body.setdefault("password", PW)
    body.setdefault("display_name", "N")
    return requests.post(base + "/api/auth/register", json=body)


# ── 가입 ───────────────────────────────────────────────

def test_한도를_넘긴_가입은_bcrypt_를_돌리지_않는다(auth_env, monkeypatch):
    import routes.auth as ra

    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "1")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    with auth_env.Session() as s:
        ra.register(ra.UserCreate(email="a@example.com", password=PW, display_name="A"), request=_req(), db=s)
    calls = []
    real = ra.hash_password
    monkeypatch.setattr(ra, "hash_password", lambda pw: calls.append(1) or real(pw))
    with auth_env.Session() as s, pytest.raises(HTTPException) as e:
        ra.register(ra.UserCreate(email="b@example.com", password=PW, display_name="B"), request=_req(), db=s)
    assert e.value.status_code == 429
    assert calls == []


def test_첫_관리자_아이디에_골뱅이와_대문자가_있어도_로그인된다(auth_env):
    assert _reg(auth_env.base, username="Admin@Corp.com").status_code == 201
    assert login(auth_env.base, "Admin@Corp.com").status_code == 200


def test_공백뿐인_이름은_422(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    assert _reg(auth_env.base, email="a@example.com", display_name="   ").status_code == 422


def test_운영의_첫_관리자_토큰에_한글이_와도_403(auth_env, monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.setenv("BOOTSTRAP_TOKEN", "t0k")
    assert _reg(auth_env.base, username="boss", bootstrap_token="토큰").status_code == 403


def test_응답에_email_verified_가_있다(auth_env):
    make_user(auth_env.Session, username="g@x.com", email="g@x.com", email_verified=True)
    body = requests.get(auth_env.base + "/api/auth/me", headers=bearer(login(auth_env.base, "g@x.com"))).json()
    assert body["email_verified"] is True


# ── 동시성 ─────────────────────────────────────────────

def test_첫_관리자_동시_가입은_IP_가_달라도_한_명(auth_env, monkeypatch):
    """같은 IP 면 가입 횟수 제한 잠금이 줄을 세워 계정 잠금을 빼도 통과한다. IP 를 갈라 계정 잠금만 남긴다."""
    import routes.auth as ra

    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "1000")
    n = 6
    barrier = threading.Barrier(n)
    out = []

    def go(i):
        with auth_env.Session() as s:
            try:
                barrier.wait()
                ra.register(ra.UserCreate(username=f"u{i}", password=PW, display_name="U"), request=_req(f"10.0.0.{i}"), db=s)
                out.append("ok")
            except HTTPException as e:
                out.append(e.status_code)

    ts = [threading.Thread(target=go, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with auth_env.Session() as s:
        assert s.query(User).filter_by(role=UserRole.admin).count() == 1
        assert s.query(User).count() == 1
    assert out.count("ok") == 1


def test_관리자_둘이_서로를_동시에_강등해도_한_명은_남는다(auth_env):
    from routes.auth import update_user_role
    from schemas import UserRoleUpdate

    a = make_user(auth_env.Session, username="a", role=UserRole.admin)
    b = make_user(auth_env.Session, username="b", role=UserRole.admin)
    barrier = threading.Barrier(2)

    def go(actor, target):
        with auth_env.Session() as s:
            try:
                me = s.get(User, actor)
                barrier.wait()
                update_user_role(target, UserRoleUpdate(role="user"), db=s, current_user=me)
            except HTTPException:
                pass

    ts = [threading.Thread(target=go, args=(a, b)), threading.Thread(target=go, args=(b, a))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with auth_env.Session() as s:
        assert s.query(User).filter_by(role=UserRole.admin, status=UserStatus.active).count() == 1


def test_강등된_관리자의_진행_중_요청은_잠금_뒤에_막힌다(auth_env, monkeypatch):
    """잠금을 기다리는 사이에 행위자가 강등되면, 잠금 안에서 다시 확인해 403."""
    import routes.auth as ra

    actor = make_user(auth_env.Session, username="actor", role=UserRole.admin)
    make_user(auth_env.Session, username="other-admin", role=UserRole.admin)
    target = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    real = ra.lock_accounts

    def demote_then_lock(db):
        with auth_env.Session() as s2:
            s2.get(User, actor).role = UserRole.user
            s2.commit()
        real(db)

    monkeypatch.setattr(ra, "lock_accounts", demote_then_lock)
    with auth_env.Session() as s:
        me = s.get(User, actor)
        with pytest.raises(HTTPException) as e:
            ra.approve_user(target, db=s, current_user=me)
    assert e.value.status_code == 403


def test_관리자_초기화는_잠금_전에_붙은_Google_연결도_끊는다(auth_env, monkeypatch):
    """초기화가 사용자를 읽은 뒤 연결이 커밋돼도, 잠금 안에서 다시 읽어 끊는다."""
    import routes.auth as ra

    boss = make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="u")
    real = ra.lock_accounts
    called = []

    def link_then_lock(db):
        called.append(1)
        with auth_env.Session() as s2:
            s2.get(User, uid).google_sub = "attacker-sub"
            s2.commit()
        real(db)

    monkeypatch.setattr(ra, "lock_accounts", link_then_lock)
    with auth_env.Session() as s:
        me = s.get(User, boss)
        ra.reset_password(uid, request=_req(), db=s, current_user=me)
    assert called, "관리자 초기화가 계정 잠금을 거치지 않았다"
    with auth_env.Session() as s:
        assert s.get(User, uid).google_sub is None


def test_비밀번호_변경은_계정_잠금을_잡는다(auth_env, monkeypatch):
    """사용 중지와 비밀번호 변경이 다른 순서로 행을 잠그면 교착된다. 같은 계정 잠금으로 줄 세운다."""
    from services.locks import LockNs
    from sqlalchemy import text

    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "300")
    make_user(auth_env.Session, username="u")
    h = bearer(login(auth_env.base, "u"))
    holder = auth_env.Session()
    try:
        holder.execute(text("SELECT pg_advisory_xact_lock(:ns, 0)"), {"ns": int(LockNs.ACCOUNTS)})
        r = requests.put(auth_env.base + "/api/auth/change-password", headers=h,
                         json={"current_password": PW, "new_password": "NewPassw0rd!"})
        assert r.status_code == 409, r.text
    finally:
        holder.rollback()
        holder.close()


# ── 비밀번호 찾기 ──────────────────────────────────────

def _approved_code(Session, uid, code="the-code-123"):
    with Session() as s:
        s.add(AccountRequest(request_type=AccountRequestType.reset_password, status=AccountRequestStatus.approved,
                             contact="x", user_id=uid, code_hash=hash_password(code),
                             code_expires_at=now_kst() + timedelta(hours=1), resolved_at=now_kst()))
        s.commit()
    return code


def test_비밀번호_찾기_완료는_Google_연결을_끊는다(auth_env):
    uid = make_user(auth_env.Session, username="u@example.com", email="u@example.com", google_sub="attacker-sub",
                    google_email="attacker@gmail.com")
    code = _approved_code(auth_env.Session, uid)
    r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                      json={"username": "U@example.com", "code": code, "new_password": "NewPassw0rd!"})
    assert r.status_code == 200, r.text
    with auth_env.Session() as s:
        u = s.get(User, uid)
        assert (u.google_sub, u.google_email) == (None, None)


@pytest.mark.parametrize("st", [UserStatus.pending, UserStatus.disabled])
def test_승인된_코드가_있어도_대기와_중지_계정은_복구_못한다(auth_env, st):
    uid = make_user(auth_env.Session, username="u@example.com", email="u@example.com", status=st)
    code = _approved_code(auth_env.Session, uid)
    r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                      json={"username": "u@example.com", "code": code, "new_password": "NewPassw0rd!"})
    assert r.status_code == 401


# ── Google ─────────────────────────────────────────────

@pytest.fixture
def gcfg(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    return auth_env


def _identity(monkeypatch, **kw):
    ident = g.GoogleIdentity(sub=kw.get("sub", "sub-1"), email=kw.get("email", "a@gmail.com"),
                             email_verified=True, hd=kw.get("hd"), name="A")
    monkeypatch.setattr(g, "exchange_and_verify", lambda cfg, code, verifier, nonce: ident)
    return ident


def _start(env, sess=None, **params):
    sess = sess or requests.Session()
    r = sess.get(env.base + "/api/auth/google/start", params=params, allow_redirects=False)
    assert r.status_code == 302, r.text
    return sess, parse_qs(urlsplit(r.headers["location"]).query)["state"][0]


def _callback(env, sess, state):
    return sess.get(env.base + "/api/auth/google/callback", params={"code": "C", "state": state}, allow_redirects=False)


def _cookie_login(env, ident):
    sess = requests.Session()
    assert sess.post(env.base + "/api/auth/login", json={"username": ident, "password": PW}).status_code == 200
    return sess


def test_확인값에_한글이_와도_500_이_아니다(gcfg, monkeypatch):
    _identity(monkeypatch)
    sess, _ = _start(gcfg)
    assert _callback(gcfg, sess, "한글").headers["location"] == "/login?error=google_state"


def test_긴_Google_이메일은_500_이_아니다(gcfg, monkeypatch):
    _identity(monkeypatch, email=("x" * 95) + "@gmail.com")
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=google_verify"


def test_이미_연결된_계정에_다른_Google_계정을_덮어쓰지_않는다(gcfg, monkeypatch):
    make_user(gcfg.Session, username="me", google_sub="sub-A")
    _identity(monkeypatch, sub="sub-B")
    sess, state = _start(gcfg, _cookie_login(gcfg, "me"), mode="link")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects?account=already_linked"
    with gcfg.Session() as s:
        assert s.query(User).filter_by(username="me").one().google_sub == "sub-A"


def test_연결_대기_중에_세션이_끊기면_연결하지_않는다(gcfg, monkeypatch):
    """세션 확인 뒤 잠금을 기다리는 사이에 비밀번호가 초기화되면(token_version 증가) 연결을 거절한다."""
    import routes.google_auth as rga

    uid = make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    sess, state = _start(gcfg, _cookie_login(gcfg, "me"), mode="link")
    real = rga.lock_accounts

    def revoke_then_lock(db):
        with gcfg.Session() as s2:
            u = s2.get(User, uid)
            u.token_version = (u.token_version or 0) + 1
            s2.commit()
        real(db)

    monkeypatch.setattr(rga, "lock_accounts", revoke_then_lock)
    assert _callback(gcfg, sess, state).headers["location"] == "/projects?account=google_state"
    with gcfg.Session() as s:
        assert s.get(User, uid).google_sub is None


def test_연결_시작에_세션이_없으면_로그인_화면으로(gcfg):
    r = requests.get(gcfg.base + "/api/auth/google/start", params={"mode": "link"}, allow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (302, "/login")


def test_Google_과_이메일_가입이_같은_주소로_동시에_와도_계정은_하나(gcfg, monkeypatch):
    import routes.auth as ra

    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "1000")
    _identity(monkeypatch, email="same@gmail.com")
    sess, state = _start(gcfg)
    barrier = threading.Barrier(2)

    def via_google():
        barrier.wait()
        _callback(gcfg, sess, state)

    def via_email():
        with gcfg.Session() as s:
            barrier.wait()
            try:
                ra.register(ra.UserCreate(email="same@gmail.com", password=PW, display_name="S"), request=_req("10.9.9.9"), db=s)
            except HTTPException:
                pass

    ts = [threading.Thread(target=via_google), threading.Thread(target=via_email)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with gcfg.Session() as s:
        assert s.query(User).filter(User.email == "same@gmail.com").count() == 1


def test_빈_DB_에서_Google_과_첫_관리자_가입이_겹쳐도_관리자는_한_명(auth_env, monkeypatch):
    import routes.auth as ra

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "1000")
    _identity(monkeypatch)
    sess, state = _start(auth_env)
    barrier = threading.Barrier(2)

    def via_google():
        barrier.wait()
        _callback(auth_env, sess, state)

    def via_register():
        with auth_env.Session() as s:
            barrier.wait()
            ra.register(ra.UserCreate(username="boss", password=PW, display_name="B"), request=_req("10.8.8.8"), db=s)

    ts = [threading.Thread(target=via_google), threading.Thread(target=via_register)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with auth_env.Session() as s:
        assert s.query(User).filter_by(role=UserRole.admin).count() == 1
