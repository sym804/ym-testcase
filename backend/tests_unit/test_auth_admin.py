"""승인, 거절, 중지, 다시 사용, 이메일 해제, 마지막 관리자 보호, 복구 경로."""
import threading

import requests
from fastapi import HTTPException

from auth_helpers import PW, bearer, login, make_user
from models import (
    AccountRequest, AccountRequestStatus, AccountRequestType, Project, ProjectMember, ProjectRole,
    User, UserRole, UserStatus,
)


def _admin(env, name="boss"):
    make_user(env.Session, username=name, role=UserRole.admin)
    return bearer(login(env.base, name))


def _post(env, h, path):
    return requests.post(env.base + path, headers=h)


def _cookie_session(env, ident):
    sess = requests.Session()
    assert sess.post(env.base + "/api/auth/login", json={"username": ident, "password": PW}).status_code == 200
    return sess


def test_승인하면_로그인된다(auth_env):
    h = _admin(auth_env)
    uid = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    assert _post(auth_env, h, f"/api/auth/users/{uid}/approve").json()["status"] == "active"
    assert login(auth_env.base, "p@example.com").status_code == 200
    assert _post(auth_env, h, f"/api/auth/users/{uid}/approve").status_code == 409


def test_거절은_대기만_지우고_멤버와_복구_이력이_있어도_된다(auth_env):
    h = _admin(auth_env)
    uid = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    with auth_env.Session() as s:
        p = Project(name="P", created_by=s.query(User).filter_by(username="boss").one().id)
        s.add(p)
        s.flush()
        s.add(ProjectMember(project_id=p.id, user_id=uid, role=ProjectRole.tester))
        s.add(AccountRequest(request_type=AccountRequestType.reset_password, status=AccountRequestStatus.approved,
                             contact="x", user_id=uid))
        s.commit()
    assert _post(auth_env, h, f"/api/auth/users/{uid}/reject").status_code == 204
    with auth_env.Session() as s:
        assert s.get(User, uid) is None
        assert s.query(AccountRequest).one().user_id is None
        assert s.query(ProjectMember).count() == 0
    active = make_user(auth_env.Session, username="a2")
    assert _post(auth_env, h, f"/api/auth/users/{active}/reject").status_code == 409


def test_중지는_키를_폐기하고_다시_사용해도_옛_키는_죽어_있다(auth_env):
    h = _admin(auth_env)
    uid = make_user(auth_env.Session, username="u1")
    uh = bearer(login(auth_env.base, "u1"))
    key = requests.post(auth_env.base + "/api/auth/api-keys", headers=uh,
                        json={"name": "k", "expires_days": 30}).json()["key"]
    assert _post(auth_env, h, f"/api/auth/users/{uid}/disable").json()["status"] == "disabled"
    assert _post(auth_env, h, f"/api/auth/users/{uid}/enable").json()["status"] == "active"
    assert requests.get(auth_env.base + "/api/auth/me", headers={"Authorization": "Bearer " + key}).status_code == 401
    assert requests.get(auth_env.base + "/api/auth/me", headers=uh).status_code == 401  # token_version 이 올랐다


def test_자기_자신과_마지막_관리자는_중지_못하고_강등도_못한다(auth_env):
    h = _admin(auth_env)
    with auth_env.Session() as s:
        boss_id = s.query(User).filter_by(username="boss").one().id
    assert _post(auth_env, h, f"/api/auth/users/{boss_id}/disable").status_code == 409
    r = requests.put(auth_env.base + f"/api/auth/users/{boss_id}/role", headers=h, json={"role": "user"})
    assert r.status_code == 409
    other = make_user(auth_env.Session, username="boss2", role=UserRole.admin)
    assert requests.put(auth_env.base + f"/api/auth/users/{other}/role", headers=h, json={"role": "user"}).status_code == 200


def test_관리자_둘이_서로를_동시에_중지해도_한_명은_남는다(auth_env):
    from routes.auth import disable_user

    a = make_user(auth_env.Session, username="a", role=UserRole.admin)
    b = make_user(auth_env.Session, username="b", role=UserRole.admin)
    barrier = threading.Barrier(2)
    results = []

    def go(actor, target):
        s = auth_env.Session()
        try:
            me = s.get(User, actor)
            barrier.wait()
            disable_user(target, db=s, current_user=me)
            results.append("ok")
        except HTTPException as e:
            results.append(e.status_code)
        finally:
            s.close()

    ts = [threading.Thread(target=go, args=(a, b)), threading.Thread(target=go, args=(b, a))]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    with auth_env.Session() as s:
        active_admins = s.query(User).filter_by(role=UserRole.admin, status=UserStatus.active).count()
    assert active_admins == 1, results
    assert sorted(map(str, results)) == ["409", "ok"]


def test_이메일_해제는_확인_안_된_이메일만(auth_env):
    h = _admin(auth_env)
    squat = make_user(auth_env.Session, username="v@corp.com", email="v@corp.com")
    google = make_user(auth_env.Session, username="g@corp.com", email="g@corp.com", email_verified=True, google_sub="s1")
    r = _post(auth_env, h, f"/api/auth/users/{squat}/release-email")
    assert (r.json()["email"], r.json()["username"]) == (None, f"released-{squat}")
    assert _post(auth_env, h, f"/api/auth/users/{google}/release-email").status_code == 409


def test_목록에_새_칸이_있다(auth_env):
    h = _admin(auth_env)
    make_user(auth_env.Session, username="g@x.com", email="g@x.com", password=None, google_sub="s2")
    rows = {u["username"]: u for u in requests.get(auth_env.base + "/api/auth/users", headers=h).json()}
    assert rows["g@x.com"]["has_password"] is False and rows["g@x.com"]["google_linked"] is True


def test_관리자_초기화는_Google_연결을_끊는다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="u", google_sub="attacker-sub")
    sess = _cookie_session(auth_env, "boss")
    r = sess.put(auth_env.base + f"/api/auth/users/{uid}/reset-password",
                 headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 200, r.text
    with auth_env.Session() as s:
        assert s.get(User, uid).google_sub is None


def test_대기_계정의_복구는_승인도_코드도_막힌다(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="p@example.com", email="p@example.com", status=UserStatus.pending)
    with auth_env.Session() as s:
        req = AccountRequest(request_type=AccountRequestType.reset_password, status=AccountRequestStatus.pending,
                             claimed_username="p@example.com", contact="x")
        s.add(req)
        s.commit()
        rid = req.id
    sess = _cookie_session(auth_env, "boss")
    r = sess.post(auth_env.base + f"/api/auth/account-requests/{rid}/approve", json={"user_id": uid},
                  headers={"X-CSRF-Token": sess.cookies.get("csrf_token")})
    assert r.status_code == 409
    r = requests.post(auth_env.base + "/api/auth/reset-password/verify",
                      json={"username": "P@example.com", "code": "whatever-code", "new_password": "NewPassw0rd!"})
    assert r.status_code == 401
