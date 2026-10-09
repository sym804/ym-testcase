"""빈 계정 삭제, Google 연결 때 빈 Google 전용 계정 정리, 연결된 Google 이메일 기록.

배경: Google 로그인으로 실수로 생긴 빈 계정이 Google 계정과 이메일을 쥐고 있으면, 본 계정에
연결해도 빈 계정이 목록에 남고 이메일도 옮겨 오지 못했다. 관리자는 그것을 지울 수도 없었다.
"""
import pytest
import requests

from auth_helpers import PW, bearer, login, make_user
from models import Project, ProjectMember, ProjectRole, User, UserRole, UserStatus
from services import google_oauth as g


def _admin_session(env, name="boss"):
    make_user(env.Session, username=name, role=UserRole.admin)
    sess = requests.Session()
    assert sess.post(env.base + "/api/auth/login", json={"username": name, "password": PW}).status_code == 200
    return sess


def _delete(env, sess, uid):
    return sess.delete(env.base + f"/api/auth/users/{uid}", headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})


def _assign(env, uid, owner):
    with env.Session() as s:
        p = Project(name="기록 있음", created_by=owner)
        s.add(p)
        s.flush()
        s.add(ProjectMember(project_id=p.id, user_id=uid, role=ProjectRole.tester))
        s.commit()


# ── 관리자 삭제 ────────────────────────────────────────

def test_활동_기록이_없는_계정은_삭제된다(auth_env):
    sess = _admin_session(auth_env)
    uid = make_user(auth_env.Session, username="g@gmail.com", email="g@gmail.com", password=None,
                    google_sub="sub-x", email_verified=True, status=UserStatus.disabled)
    assert _delete(auth_env, sess, uid).status_code == 204
    with auth_env.Session() as s:
        assert s.get(User, uid) is None


def test_작업_기록이_있는_계정은_삭제하지_않는다(auth_env):
    sess = _admin_session(auth_env)
    with auth_env.Session() as s:
        boss = s.query(User).filter_by(username="boss").one().id
    uid = make_user(auth_env.Session, username="worker")
    _assign(auth_env, uid, boss)
    r = _delete(auth_env, sess, uid)
    assert r.status_code == 409
    assert "사용 중지" in r.json()["detail"]
    with auth_env.Session() as s:
        assert s.get(User, uid) is not None
        assert s.query(ProjectMember).filter_by(user_id=uid).count() == 1


def test_자기_자신은_삭제하지_않는다(auth_env):
    sess = _admin_session(auth_env)
    with auth_env.Session() as s:
        boss = s.query(User).filter_by(username="boss").one().id
    assert _delete(auth_env, sess, boss).status_code == 409


def test_삭제는_관리자만(auth_env):
    uid = make_user(auth_env.Session, username="target")
    make_user(auth_env.Session, username="plain")
    assert requests.delete(auth_env.base + f"/api/auth/users/{uid}").status_code == 401
    assert requests.delete(auth_env.base + f"/api/auth/users/{uid}",
                           headers=bearer(login(auth_env.base, "plain"))).status_code == 403
    with auth_env.Session() as s:
        assert s.get(User, uid) is not None


def test_없는_계정은_404(auth_env):
    sess = _admin_session(auth_env)
    assert _delete(auth_env, sess, 99999).status_code == 404


# ── Google 연결 ────────────────────────────────────────

@pytest.fixture
def gcfg(auth_env, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "sec")
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    return auth_env


def _identity(monkeypatch, sub="sub-1", email="g@gmail.com"):
    ident = g.GoogleIdentity(sub=sub, email=email, email_verified=True, hd=None, name="G")
    monkeypatch.setattr(g, "exchange_and_verify", lambda cfg, code, verifier, nonce: ident)


def _login_session(env, username):
    sess = requests.Session()
    assert sess.post(env.base + "/api/auth/login", json={"username": username, "password": PW}).status_code == 200
    return sess


def _google(env, sess, mode="login"):
    from urllib.parse import parse_qs, urlsplit
    r = sess.get(env.base + "/api/auth/google/start", params={"mode": mode}, allow_redirects=False)
    state = parse_qs(urlsplit(r.headers["location"]).query)["state"][0]
    return sess.get(env.base + "/api/auth/google/callback", params={"code": "C", "state": state},
                    allow_redirects=False).headers["location"]


def _google_only(env, **kw):
    return make_user(env.Session, username="g@gmail.com", email="g@gmail.com", password=None,
                     google_sub="sub-1", google_email="g@gmail.com", email_verified=True, **kw)


def test_빈_Google_전용_계정에_묶인_Google_계정을_연결하면_정리하고_옮긴다(gcfg, monkeypatch):
    stray = _google_only(gcfg)
    me = make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=merged"
    with gcfg.Session() as s:
        assert s.get(User, stray) is None
        u = s.get(User, me)
        assert (u.google_sub, u.google_email, u.email, u.email_verified) == (
            "sub-1", "g@gmail.com", "g@gmail.com", True)


def test_중지된_빈_Google_전용_계정도_정리한다(gcfg, monkeypatch):
    stray = _google_only(gcfg, status=UserStatus.disabled)
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=merged"
    with gcfg.Session() as s:
        assert s.get(User, stray) is None


def test_작업_기록이_있는_Google_전용_계정이면_옮기지_않는다(gcfg, monkeypatch):
    stray = _google_only(gcfg)
    with gcfg.Session() as s:
        boss = s.query(User).filter_by(username="boss").one().id
    _assign(gcfg, stray, boss)
    me = make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=already_linked"
    with gcfg.Session() as s:
        assert s.get(User, stray).google_sub == "sub-1"
        assert s.get(User, me).google_sub is None


def test_비밀번호가_있는_계정이면_옮기지_않는다(gcfg, monkeypatch):
    owner = make_user(gcfg.Session, username="owner", google_sub="sub-1")
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=already_linked"
    with gcfg.Session() as s:
        assert s.get(User, owner).google_sub == "sub-1"


def test_마지막_활성_관리자인_빈_계정은_옮기지_않는다(gcfg, monkeypatch):
    stray = _google_only(gcfg, role=UserRole.admin)
    with gcfg.Session() as s:
        s.query(User).filter_by(username="boss").one().status = UserStatus.disabled
        s.commit()
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=already_linked"
    with gcfg.Session() as s:
        assert s.get(User, stray) is not None


# ── 연결된 Google 이메일 기록 ───────────────────────────

def test_새_Google_계정은_연결_이메일을_남긴다(gcfg, monkeypatch):
    _identity(monkeypatch, email="new@gmail.com")
    _google(gcfg, requests.Session())
    with gcfg.Session() as s:
        assert s.query(User).filter_by(google_sub="sub-1").one().google_email == "new@gmail.com"


def test_Google_로그인할_때마다_연결_이메일을_최신으로(gcfg, monkeypatch):
    uid = make_user(gcfg.Session, username="me", google_sub="sub-1")  # 이 기능 전에 연결된 계정(기록 없음)
    _identity(monkeypatch, email="me@gmail.com")
    assert _google(gcfg, requests.Session()) == "/projects"
    with gcfg.Session() as s:
        assert s.get(User, uid).google_email == "me@gmail.com"


def test_이메일을_다른_계정이_쥐고_있어도_연결_이메일은_남는다(gcfg, monkeypatch):
    make_user(gcfg.Session, username="holder", email="g@gmail.com")  # 비밀번호가 있어 정리 대상 아님
    me = make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=linked"
    with gcfg.Session() as s:
        u = s.get(User, me)
        assert (u.email, u.google_email) == (None, "g@gmail.com")


def test_연결_해제는_연결_이메일도_지우고_응답에_실린다(gcfg, monkeypatch):
    me = make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    sess = _login_session(gcfg, "me")
    _google(gcfg, sess, "link")
    users = requests.get(gcfg.base + "/api/auth/users", headers=bearer(login(gcfg.base, "boss"))).json()
    assert next(u for u in users if u["id"] == me)["google_email"] == "g@gmail.com"
    r = sess.post(gcfg.base + "/api/auth/google/unlink", headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 200 and r.json()["google_email"] is None


# ── QA 지적 보강 ───────────────────────────────────────

def _revoked_key(env, uid):
    from datetime import datetime
    from models import ApiKey
    with env.Session() as s:
        s.add(ApiKey(user_id=uid, name="old", key_id=f"k{uid:015d}", key_hash="0" * 64, revoked_at=datetime.now()))
        s.commit()


def test_폐기된_API_키만_있어도_삭제하지_않고_키도_남는다(auth_env):
    """api_keys 는 ON DELETE CASCADE 라 기록 집계에서 빠지면 키가 조용히 지워진다."""
    from models import ApiKey
    sess = _admin_session(auth_env)
    uid = make_user(auth_env.Session, username="keyonly", password=None, google_sub="sub-k")
    _revoked_key(auth_env, uid)
    assert _delete(auth_env, sess, uid).status_code == 409
    with auth_env.Session() as s:
        assert s.query(ApiKey).filter_by(user_id=uid).count() == 1


def test_프로젝트를_만든_기록이_있으면_삭제하지_않는다(auth_env):
    """CASCADE 가 아닌 외래키(projects.created_by)도 기록으로 센다."""
    sess = _admin_session(auth_env)
    uid = make_user(auth_env.Session, username="creator")
    with auth_env.Session() as s:
        s.add(Project(name="만든 사람", created_by=uid))
        s.commit()
    assert _delete(auth_env, sess, uid).status_code == 409


def test_삭제가_배정_저장을_기다렸다가_기록을_보고_거절한다(auth_env):
    """배정이 아직 커밋 전이면 삭제의 행 잠금이 기다리고, 커밋된 배정을 세서 409 를 낸다."""
    import threading
    import time
    sess = _admin_session(auth_env)
    with auth_env.Session() as s:
        boss = s.query(User).filter_by(username="boss").one().id
        p = Project(name="경합", created_by=boss)
        s.add(p)
        s.commit()
        pid = p.id
    uid = make_user(auth_env.Session, username="racer")
    holder = auth_env.Session()
    try:
        holder.add(ProjectMember(project_id=pid, user_id=uid, role=ProjectRole.tester))
        holder.flush()  # 외래키 검사로 사용자 행에 KEY SHARE 잠금이 걸린다
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("r", _delete(auth_env, sess, uid)))
        t.start()
        time.sleep(1.0)
        assert t.is_alive(), "삭제가 배정 트랜잭션을 기다리지 않았다"
        holder.commit()
        t.join(timeout=20)
    finally:
        holder.close()
    assert out["r"].status_code == 409
    with auth_env.Session() as s:
        assert s.query(ProjectMember).filter_by(user_id=uid).count() == 1


def test_승인_대기_빈_Google_계정도_정리한다(gcfg, monkeypatch):
    stray = _google_only(gcfg, status=UserStatus.pending)
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=merged"
    with gcfg.Session() as s:
        assert s.get(User, stray) is None


def test_API_키가_있는_Google_전용_계정은_옮기지_않는다(gcfg, monkeypatch):
    stray = _google_only(gcfg)
    _revoked_key(gcfg, stray)
    make_user(gcfg.Session, username="me")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=already_linked"
    with gcfg.Session() as s:
        assert s.get(User, stray) is not None


def test_정리된_계정의_기존_세션은_더_쓸_수_없다(gcfg, monkeypatch):
    _google_only(gcfg)
    _identity(monkeypatch)
    old = requests.Session()
    assert _google(gcfg, old) == "/projects"  # 빈 계정으로 로그인해 둔 세션
    assert old.get(gcfg.base + "/api/auth/me").status_code == 200
    make_user(gcfg.Session, username="me")
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=merged"
    assert old.get(gcfg.base + "/api/auth/me").status_code == 401


def test_이미_이메일이_있는_계정은_이메일을_바꾸지_않고_Google_주소만_남긴다(gcfg, monkeypatch):
    stray = _google_only(gcfg)
    me = make_user(gcfg.Session, username="me", email="me@corp.com")
    _identity(monkeypatch)
    assert _google(gcfg, _login_session(gcfg, "me"), "link") == "/projects?account=merged"
    with gcfg.Session() as s:
        assert s.get(User, stray) is None
        u = s.get(User, me)
        assert (u.email, u.google_email) == ("me@corp.com", "g@gmail.com")
