"""Google 콜백: 로그인, 신규, 대기, 회사 계정만, 이메일 선점, 상태, 연결, 해제, 동시성."""
import threading
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from auth_helpers import PW, make_user
from models import User, UserRole, UserStatus
from services import google_oauth as g


@pytest.fixture
def gcfg(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    return auth_env


def _identity(monkeypatch, **kw):
    ident = g.GoogleIdentity(sub=kw.get("sub", "sub-1"), email=kw.get("email", "a@gmail.com"),
                             email_verified=kw.get("email_verified", True), hd=kw.get("hd"), name=kw.get("name", "A"))
    monkeypatch.setattr(g, "exchange_and_verify", lambda cfg, code, verifier, nonce: ident)
    return ident


def _start(env, sess=None, **params):
    sess = sess or requests.Session()
    r = sess.get(env.base + "/api/auth/google/start", params=params, allow_redirects=False)
    assert r.status_code == 302, r.text
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    return sess, state


def _callback(env, sess, state, **extra):
    params = {"code": "C", "state": state, **extra}
    return sess.get(env.base + "/api/auth/google/callback", params=params, allow_redirects=False)


def _cookie_login(env, ident):
    sess = requests.Session()
    assert sess.post(env.base + "/api/auth/login", json={"username": ident, "password": PW}).status_code == 200
    return sess


def test_시작은_Google_로_보내고_쿠키를_심는다(gcfg):
    r = requests.get(gcfg.base + "/api/auth/google/start", allow_redirects=False)
    assert r.headers["location"].startswith(g.AUTH_URI)
    cookie = r.headers["set-cookie"]
    assert "oauth_flow=" in cookie and "Path=/api/auth/google" in cookie and "HttpOnly" in cookie
    assert "samesite=lax" in cookie.lower()


def test_Google_이_꺼져_있으면_안내(auth_env):
    r = requests.get(auth_env.base + "/api/auth/google/start", allow_redirects=False)
    assert r.headers["location"] == "/login?error=google_disabled"


def test_새_계정이_만들어지고_로그인된다(gcfg, monkeypatch):
    _identity(monkeypatch, email="new@gmail.com")
    sess, state = _start(gcfg, next="/projects/3")
    r = _callback(gcfg, sess, state)
    assert r.headers["location"] == "/projects/3"
    assert "access_token" in sess.cookies
    with gcfg.Session() as s:
        u = s.query(User).filter_by(google_sub="sub-1").one()
        assert (u.username, u.email, u.email_verified, u.password_hash, u.status) == (
            "new@gmail.com", "new@gmail.com", True, None, UserStatus.active)


def test_개인_계정은_personal_에서_대기(gcfg, monkeypatch):
    monkeypatch.setenv("AUTH_APPROVAL", "personal")
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=pending"
    assert "access_token" not in sess.cookies


def test_회사_계정은_personal_에서_바로(gcfg, monkeypatch):
    monkeypatch.setenv("AUTH_APPROVAL", "personal")
    monkeypatch.setenv("AUTH_COMPANY_DOMAINS", "corp.com")
    _identity(monkeypatch, email="a@corp.com", hd="corp.com")
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/projects"


def test_회사_계정만이면_개인은_거절(gcfg, monkeypatch):
    monkeypatch.setenv("AUTH_ALLOW_PERSONAL", "0")
    monkeypatch.setenv("AUTH_COMPANY_DOMAINS", "corp.com")
    _identity(monkeypatch, email="a@corp.com", hd=None)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=company_only"


def test_같은_이메일의_계정이_있으면_만들지_않는다(gcfg, monkeypatch):
    make_user(gcfg.Session, username="a@gmail.com", email="a@gmail.com")
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=email_taken"
    with gcfg.Session() as s:
        assert s.query(User).filter_by(google_sub="sub-1").first() is None


@pytest.mark.parametrize("st,code", [(UserStatus.pending, "pending"), (UserStatus.disabled, "disabled")])
def test_연결된_계정의_상태(gcfg, monkeypatch, st, code):
    make_user(gcfg.Session, username="x", google_sub="sub-1", status=st)
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == f"/login?error={code}"


def test_확인값이_없거나_다르면_거절(gcfg, monkeypatch):
    _identity(monkeypatch)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, "other-state").headers["location"] == "/login?error=google_state"
    r = requests.get(gcfg.base + "/api/auth/google/callback", params={"code": "C", "state": state}, allow_redirects=False)
    assert r.headers["location"] == "/login?error=google_state"


def test_검증_실패와_이메일_미확인(gcfg, monkeypatch):
    def boom(cfg, code, verifier, nonce):
        raise g.GoogleAuthError("x")
    monkeypatch.setattr(g, "exchange_and_verify", boom)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=google_verify"
    _identity(monkeypatch, email_verified=False)
    sess, state = _start(gcfg)
    assert _callback(gcfg, sess, state).headers["location"] == "/login?error=google_email_unverified"


def test_취소하면_메시지_없이_로그인_화면(gcfg):
    sess, state = _start(gcfg)
    r = sess.get(gcfg.base + "/api/auth/google/callback", params={"error": "access_denied", "state": state},
                 allow_redirects=False)
    assert r.headers["location"] == "/login"


def test_빈_DB_는_첫_관리자부터(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    _identity(monkeypatch)
    sess, state = _start(auth_env)
    assert _callback(auth_env, sess, state).headers["location"] == "/login?error=bootstrap_required"


def test_사이트_밖_이동_경로는_버린다(gcfg, monkeypatch):
    _identity(monkeypatch)
    sess, state = _start(gcfg, next="/\\evil.com")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects"


def test_연결과_해제(gcfg, monkeypatch):
    uid = make_user(gcfg.Session, username="me")
    _identity(monkeypatch, email="me@gmail.com")
    sess = _cookie_login(gcfg, "me")
    sess, state = _start(gcfg, sess, mode="link")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects?account=linked"
    with gcfg.Session() as s:
        u = s.get(User, uid)
        assert (u.google_sub, u.email, u.email_verified) == ("sub-1", "me@gmail.com", True)
    r = sess.post(gcfg.base + "/api/auth/google/unlink", headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 200 and r.json()["google_linked"] is False


def test_비밀번호_없는_계정은_해제_못한다(gcfg, monkeypatch):
    make_user(gcfg.Session, username="g@gmail.com", email="g@gmail.com", password=None, google_sub="sub-1")
    _identity(monkeypatch, email="g@gmail.com")
    sess, state = _start(gcfg)
    _callback(gcfg, sess, state)
    r = sess.post(gcfg.base + "/api/auth/google/unlink", headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 400


def test_연결은_시작한_사람과_세션이_같아야(gcfg, monkeypatch):
    make_user(gcfg.Session, username="alice")
    make_user(gcfg.Session, username="mallory")
    _identity(monkeypatch)
    victim = _cookie_login(gcfg, "alice")
    attacker = _cookie_login(gcfg, "mallory")
    attacker, state = _start(gcfg, attacker, mode="link")
    flow_cookie = attacker.cookies.get("oauth_flow")
    victim.cookies.set("oauth_flow", flow_cookie, domain="127.0.0.1", path="/api/auth/google")
    assert _callback(gcfg, victim, state).headers["location"] == "/projects?account=google_state"


def test_이미_다른_계정에_연결된_Google_계정(gcfg, monkeypatch):
    make_user(gcfg.Session, username="owner", google_sub="sub-1")
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    sess, state = _start(gcfg, _cookie_login(gcfg, "me"), mode="link")
    assert _callback(gcfg, sess, state).headers["location"] == "/projects?account=already_linked"


def test_로그인_안_했으면_연결_시작은_401_중지된_세션도(gcfg):
    assert requests.get(gcfg.base + "/api/auth/google/start", params={"mode": "link"},
                        allow_redirects=False).status_code == 401
    uid = make_user(gcfg.Session, username="soon-disabled")
    sess = _cookie_login(gcfg, "soon-disabled")
    with gcfg.Session() as s:
        s.get(User, uid).status = UserStatus.disabled
        s.commit()
    assert sess.get(gcfg.base + "/api/auth/google/start", params={"mode": "link"},
                    allow_redirects=False).status_code == 401


def test_같은_Google_계정의_동시_첫_로그인은_계정_하나(gcfg, monkeypatch):
    _identity(monkeypatch)
    pairs = [_start(gcfg) for _ in range(2)]
    barrier = threading.Barrier(2)
    out = []

    def go(sess, state):
        barrier.wait()
        out.append(_callback(gcfg, sess, state).headers["location"])

    ts = [threading.Thread(target=go, args=p) for p in pairs]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with gcfg.Session() as s:
        assert s.query(User).filter_by(google_sub="sub-1").count() == 1
    assert out == ["/projects", "/projects"]
