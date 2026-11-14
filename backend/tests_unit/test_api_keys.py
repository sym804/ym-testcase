"""API 키

- 발급 원문은 한 번만, 목록에는 해시도 원문도 없다.
- 키로 인증하면 키 주인으로 동작하고 프로젝트 권한도 그대로다.
- 폐기 · 만료 · 틀린 비밀은 401. 어느 단계에서 막혔는지는 같은 문구.
- 키로는 키 관리 · 비밀번호 변경 · 로그아웃 · 관리자 초기화 · 복구 승인을 못 한다.
- 비밀번호가 바뀌면(본인 · 관리자 초기화) 그 사용자의 키가 모두 폐기된다.
- 키에는 범위가 있다(SYM-217). 결과 업로드 전용 키는 업로드 경로만 부른다. 새 키의 기본값이다.
- 시스템 역할(QA Manager 이상)이 필요한 작업은 범위와 관계없이 키로 못 한다.

실행: cd backend && python -m pytest tests_unit/test_api_keys.py -q
"""
import os
import socket
import sys
import threading
import time
from datetime import timedelta

import pytest
import requests
import uvicorn

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy.orm import sessionmaker

from auth import hash_password
from database import get_db
from main import app
from models import ApiKey, Project, ProjectMember, ProjectRole, User, UserRole, UserStatus, now_kst

PW = "Passw0rd!long"


class _Client:
    """requests 를 base URL 에 묶은 것. 쿠키를 들고 다니지 않아 헤더 인증만 시험한다."""

    def __init__(self, base):
        self.base = base

    def get(self, path, **kw):
        return requests.get(self.base + path, **kw)

    def post(self, path, **kw):
        return requests.post(self.base + path, **kw)

    def put(self, path, **kw):
        return requests.put(self.base + path, **kw)

    def delete(self, path, **kw):
        return requests.delete(self.base + path, **kw)


@pytest.fixture(scope="module")
def server():
    """임시 DB 를 붙인 앱을 빈 포트에 띄운다. httpx2 없이 실제 HTTP 로 인증 흐름을 본다.

    lifespan 을 끄므로 개발 DB 에 마이그레이션이 돌지 않는다. DB 는 env 픽스처가 갈아 끼운다.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, lifespan="off", log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    deadline = time.time() + 15
    while not srv.started and time.time() < deadline:
        time.sleep(0.05)
    assert srv.started, "테스트 서버가 뜨지 않았다"
    yield _Client(f"http://127.0.0.1:{port}")
    srv.should_exit = True
    th.join(timeout=10)


@pytest.fixture
def env(pg_engine, tmp_path, server):
    engine = pg_engine

    Session = sessionmaker(bind=engine)
    db = Session()
    admin = User(username="boss", password_hash=hash_password(PW), display_name="B", role=UserRole.admin)
    user = User(username="ym", password_hash=hash_password(PW), display_name="Y", role=UserRole.user)
    db.add_all([admin, user])
    db.flush()
    p = Project(name="P", created_by=user.id, is_private=True)
    db.add(p)
    db.flush()
    # 실제 생성 경로처럼 생성자를 admin 멤버로 둔다(역할은 멤버 표로만 판정한다)
    db.add(ProjectMember(project_id=p.id, user_id=user.id, role=ProjectRole.admin))
    db.commit()

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    from services import rate_limit
    rate_limit.clear_all(engine=engine)
    yield server, db
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def _session(client, username="ym"):
    r = client.post("/api/auth/login", json={"username": username, "password": PW})
    assert r.status_code == 200, r.text
    # 쿠키는 버리고 헤더로만 인증한다(CSRF 없이 상태 변경을 시험하려고)
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def _new_key(client, h, name="CI", days=90, scope="full"):
    body = {"name": name, "expires_days": days}
    if scope is not None:
        body["scope"] = scope
    r = client.post("/api/auth/api-keys", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _bearer(raw):
    return {"Authorization": "Bearer " + raw}


def test_발급_원문은_한_번만_목록에는_없다(env):
    client, db = env
    h = _session(client)
    k = _new_key(client, h)
    assert k["key"].startswith("ymtc_") and k["key"].startswith(k["prefix"] + "_")
    assert k["status"] == "active" and k["expires_at"] is not None
    listed = client.get("/api/auth/api-keys", headers=h).json()
    assert len(listed) == 1 and "key" not in listed[0] and "key_hash" not in listed[0]
    row = db.query(ApiKey).one()
    assert row.key_hash != k["key"] and len(row.key_hash) == 64, "원문을 저장하지 않는다"


def test_키로_인증하면_주인으로_동작하고_프로젝트_권한도_같다(env):
    client, db = env
    raw = _new_key(client, _session(client))["key"]
    me = client.get("/api/auth/me", headers=_bearer(raw))
    assert me.status_code == 200 and me.json()["username"] == "ym"
    assert client.get("/api/projects/1/testruns", headers=_bearer(raw)).status_code == 200
    db.expire_all()
    assert db.query(ApiKey).one().last_used_at is not None


def test_남의_비공개_프로젝트는_키로도_막힌다(env):
    client, _ = env
    db = env[1]
    db.add(Project(name="Q", created_by=1, is_private=True))
    db.commit()
    raw = _new_key(client, _session(client))["key"]
    assert client.get("/api/projects/2/testruns", headers=_bearer(raw)).status_code == 403


@pytest.mark.parametrize("mutate", ["revoke", "expire", "wrong_secret", "garbage", "unknown_id"])
def test_쓸_수_없는_키는_401_이고_문구가_같다(env, mutate):
    client, db = env
    h = _session(client)
    k = _new_key(client, h)
    raw = k["key"]
    if mutate == "revoke":
        assert client.delete(f"/api/auth/api-keys/{k['id']}", headers=h).json()["status"] == "revoked"
    elif mutate == "expire":
        row = db.query(ApiKey).one()
        row.expires_at = now_kst() - timedelta(seconds=1)
        db.commit()
    elif mutate == "wrong_secret":
        raw = raw[:-4] + ("AAAA" if not raw.endswith("AAAA") else "BBBB")
    elif mutate == "garbage":
        raw = "ymtc_"
    elif mutate == "unknown_id":
        raw = "ymtc_00000000_" + raw.split("_", 2)[2]
    r = client.get("/api/auth/me", headers=_bearer(raw))
    assert r.status_code == 401 and r.json()["detail"] == "유효하지 않은 API 키입니다."


def test_키로는_세션_전용_작업을_못_한다(env):
    client, db = env
    h = _session(client)
    raw = _new_key(client, h)["key"]
    k = _bearer(raw)
    assert client.get("/api/auth/api-keys", headers=k).status_code == 403
    assert client.post("/api/auth/api-keys", json={"name": "x"}, headers=k).status_code == 403
    assert client.post("/api/auth/logout", headers=k).status_code == 403
    r = client.put("/api/auth/change-password", json={"current_password": PW, "new_password": "Another1!pw"}, headers=k)
    assert r.status_code == 403
    db.expire_all()
    assert db.query(User).filter_by(username="ym").one().token_version == 0, "로그아웃이 웹 세션을 끊지 않았다"


def test_관리자_키로는_비밀번호_초기화와_복구_승인을_못_한다(env):
    client, _ = env
    raw = _new_key(client, _session(client, "boss"))["key"]
    assert client.put("/api/auth/users/2/reset-password", headers=_bearer(raw)).status_code == 403
    # 요청 행이 없어도 403 이 먼저 나야 한다. 세션 검사가 조회보다 앞이다
    r = client.post("/api/auth/account-requests/1/approve", json={"user_id": 2}, headers=_bearer(raw))
    assert r.status_code == 403


@pytest.mark.parametrize("method,path,body", [
    ("post", "/api/auth/users/2/approve", None),
    ("post", "/api/auth/users/2/reject", None),
    ("post", "/api/auth/users/2/disable", None),
    ("post", "/api/auth/users/2/enable", None),
    ("post", "/api/auth/users/2/release-email", None),
    ("delete", "/api/auth/users/2", None),
    ("put", "/api/auth/users/2/role", {"role": "admin"}),
    ("post", "/api/auth/account-requests/1/reject", {"reason": "x"}),
])
def test_관리자_키로는_계정을_관리하지_못한다(env, method, path, body):
    """유출된 관리자 키로 자기 계정을 승인하고 관리자로 올리면 키를 폐기해도 관리자가 남는다."""
    client, db = env
    raw = _new_key(client, _session(client, "boss"))["key"]
    kw = {"headers": _bearer(raw)}
    if body is not None:
        kw["json"] = body
    r = getattr(client, method)(path, **kw)
    assert r.status_code == 403, r.text
    db.expire_all()
    ym = db.query(User).filter_by(username="ym").one()
    assert ym.role == UserRole.user and ym.status == UserStatus.active


def test_비밀번호를_바꾸면_키가_모두_폐기된다(env):
    client, _ = env
    h = _session(client)
    raw1 = _new_key(client, h, "a")["key"]
    raw2 = _new_key(client, h, "b")["key"]
    r = client.put("/api/auth/change-password", json={"current_password": PW, "new_password": "Another1!pw"}, headers=h)
    assert r.status_code == 200
    assert client.get("/api/auth/me", headers=_bearer(raw1)).status_code == 401
    assert client.get("/api/auth/me", headers=_bearer(raw2)).status_code == 401


def test_관리자가_초기화하면_대상의_키가_폐기되고_관리자_키는_남는다(env):
    client, _ = env
    boss = _session(client, "boss")
    boss_key = _new_key(client, boss)["key"]
    ym_key = _new_key(client, _session(client))["key"]
    assert client.put("/api/auth/users/2/reset-password", headers=boss).status_code == 200
    assert client.get("/api/auth/me", headers=_bearer(ym_key)).status_code == 401
    assert client.get("/api/auth/me", headers=_bearer(boss_key)).status_code == 200


def test_남의_키는_폐기할_수_없다(env):
    client, _ = env
    k = _new_key(client, _session(client, "boss"))
    r = client.delete(f"/api/auth/api-keys/{k['id']}", headers=_session(client))
    assert r.status_code == 404
    assert client.get("/api/auth/me", headers=_bearer(k["key"])).status_code == 200


def test_만료_선택지와_이름_검증(env):
    client, _ = env
    h = _session(client)
    assert client.post("/api/auth/api-keys", json={"name": "x", "expires_days": 7}, headers=h).status_code == 422
    assert client.post("/api/auth/api-keys", json={"name": "   "}, headers=h).status_code == 422
    k = _new_key(client, h, days=None)
    assert k["expires_at"] is None and k["status"] == "active"


def test_살아_있는_키는_20개까지(env):
    client, _ = env
    h = _session(client)
    ids = [_new_key(client, h, f"k{i}")["id"] for i in range(20)]
    r = client.post("/api/auth/api-keys", json={"name": "21"}, headers=h)
    assert r.status_code == 400 and "20" in r.json()["detail"]
    client.delete(f"/api/auth/api-keys/{ids[0]}", headers=h)
    assert client.post("/api/auth/api-keys", json={"name": "21"}, headers=h).status_code == 201


def test_JWT_는_예전처럼_통한다(env):
    client, _ = env
    assert client.get("/api/auth/me", headers=_session(client)).json()["username"] == "ym"



# ── 키 범위 (SYM-217) ────────────────────────────────────────────────────────

def test_새_키의_기본_범위는_결과_업로드_전용이다(env):
    client, db = env
    k = _new_key(client, _session(client), scope=None)
    assert k["scope"] == "results"
    listed = client.get("/api/auth/api-keys", headers=_session(client)).json()
    assert listed[0]["scope"] == "results"


def test_범위는_정해진_값만_받는다(env):
    client, db = env
    r = client.post("/api/auth/api-keys", json={"name": "x", "expires_days": 30, "scope": "admin"},
                    headers=_session(client))
    assert r.status_code == 422


def test_결과_업로드_전용_키는_업로드_경로만_부른다(env):
    client, db = env
    raw = _new_key(client, _session(client), scope="results")["key"]
    h = _bearer(raw)
    assert client.get("/api/auth/me", headers=h).status_code == 200
    up = client.post("/api/uploads", headers=h, json={
        "purpose": "result_import", "filename": "r.json", "size": 10, "content_type": None})
    assert up.status_code == 201, up.text
    # 결과 가져오기 경로는 범위 검사를 통과한다(파일이 없어 그 뒤에서 막히는 것은 범위와 무관)
    imp = client.post("/api/projects/1/testruns/import?run_name=x", headers=h)
    assert imp.json().get("detail") != "이 API 키의 범위로는 할 수 없는 작업입니다.", imp.text
    denied = [
        ("get", "/api/projects", None),
        ("get", "/api/projects/1/testruns", None),
        ("get", "/api/projects/1/testcases", None),
        ("post", "/api/projects", {"name": "new"}),
        ("post", "/api/uploads", {"purpose": "attachment", "filename": "a.png", "size": 10, "content_type": None}),
        ("post", "/api/uploads", {"purpose": "tc_import", "filename": "a.xlsx", "size": 10, "content_type": None}),
    ]
    for method, path, body in denied:
        kw = {"headers": h}
        if body is not None:
            kw["json"] = body
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 403, (method, path, r.status_code, r.text)
        assert r.json()["detail"] == "이 API 키의 범위로는 할 수 없는 작업입니다."


def test_범위가_없던_기존_키는_전체_범위다(env):
    """범위 칸이 비어 들어온 행은 전체 범위다(모델 server_default). 마이그레이션 쪽은
    test_api_key_scope_migration.py 가 0009 에서 올려 확인한다."""
    client, db = env
    from sqlalchemy import text
    raw = _new_key(client, _session(client), scope="full")["key"]
    row = db.query(ApiKey).one()
    db.execute(text("INSERT INTO api_keys (user_id, name, key_id, key_hash) VALUES (:u, 'old', 'oldkey01', :h)"),
               {"u": row.user_id, "h": "0" * 64})
    db.commit()
    assert db.execute(text("SELECT scope FROM api_keys WHERE key_id = 'oldkey01'")).scalar() == "full"
    assert client.get("/api/projects/1/testruns", headers=_bearer(raw)).status_code == 200


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/auth/users", None),
    ("get", "/api/auth/account-requests", None),
    ("get", "/api/projects/all-assignments", None),
    ("post", "/api/projects/assign-all", {"user_id": 2, "role": "admin"}),
])
def test_전체_범위_관리자_키로도_시스템_관리_경로는_못_부른다(env, method, path, body):
    """관리자 키 하나로 전 사용자 이메일을 읽고 일괄 배정을 부를 수 있었다. 범위가 full 이어도 막는다."""
    client, db = env
    hs = _session(client, "boss")
    raw = _new_key(client, hs, scope="full")["key"]
    kw = {"headers": _bearer(raw)}
    if body is not None:
        kw["json"] = body
    r = getattr(client, method)(path, **kw)
    assert r.status_code == 403, r.text
    db.expire_all()
    assert db.query(ProjectMember).filter_by(user_id=2).count() == 1
    # 같은 작업을 세션으로는 할 수 있다
    kw["headers"] = hs
    assert getattr(client, method)(path, **kw).status_code == 200


@pytest.mark.parametrize("state", [UserStatus.disabled, UserStatus.pending])
def test_일괄_배정은_사용_중인_계정만_받는다(env, state):
    client, db = env
    db.query(User).filter_by(username="ym").update({User.status: state})
    db.commit()
    r = client.post("/api/projects/assign-all", headers=_session(client, "boss"), json={"user_id": 2, "role": "admin"})
    assert (r.status_code, r.json()["detail"]) == (409, "사용 중인 계정만 처리할 수 있습니다.")
    db.expire_all()
    assert db.query(ProjectMember).filter_by(user_id=2).count() == 1



RESULT_JSON = (b'{"suites": [{"title": "a.spec.mjs", "specs": [{"title": "CI-01 login", '
               b'"tests": [{"status": "expected", "expectedStatus": "passed", "annotations": [], '
               b'"results": [{"status": "passed", "duration": 10}]}]}]}]}')


def test_결과_업로드_전용_키로_결과를_실제로_올린다(env):
    """범위가 경로만 열고 그 뒤 처리가 실패하면 CI 가 깨진다. 두 가져오기 경로 모두 끝까지 확인한다."""
    client, db = env
    from models import TestCase, TestResult, TestResultValue, TestRun
    ym = db.query(User).filter_by(username="ym").one()
    db.add(TestCase(project_id=1, no=1, tc_id="CI-01", sheet_name="S", created_by=ym.id))
    db.commit()
    h = _bearer(_new_key(client, _session(client), scope="results")["key"])
    files = {"file": ("results.json", RESULT_JSON, "application/json")}
    r = client.post("/api/projects/1/testruns/import?run_name=CI", headers=h, files=files)
    assert r.status_code == 200, r.text
    db.expire_all()
    run = db.query(TestRun).filter_by(project_id=1, name="CI").one()
    assert db.query(TestResult).filter_by(test_run_id=run.id).one().result == TestResultValue.PASS
    # 같은 회차에 실패 결과를 올려 실제로 바뀌는지 본다(200 만 보면 저장을 빼먹어도 통과한다)
    failed = RESULT_JSON.replace(b'"status": "expected"', b'"status": "unexpected"').replace(
        b'"results": [{"status": "passed", "duration": 10}]',
        b'"results": [{"status": "failed", "duration": 10, "error": {"message": "x"}}]')
    r = client.post(f"/api/projects/1/testruns/{run.id}/results/import?keep_executed=false", headers=h,
                    files={"file": ("results.json", failed, "application/json")})
    assert r.status_code == 200, r.text
    db.expire_all()
    assert db.query(TestResult).filter_by(test_run_id=run.id).one().result == TestResultValue.FAIL


def test_결과_업로드_전용_키도_남의_프로젝트에는_못_올린다(env):
    client, db = env
    boss = db.query(User).filter_by(username="boss").one()
    other = Project(name="Q", created_by=boss.id, is_private=True)
    db.add(other)
    db.commit()
    h = _bearer(_new_key(client, _session(client), scope="results")["key"])
    r = client.post(f"/api/projects/{other.id}/testruns/import?run_name=CI", headers=h,
                    files={"file": ("results.json", RESULT_JSON, "application/json")})
    assert r.status_code in (403, 404), r.text
    assert r.json()["detail"] != "이 API 키의 범위로는 할 수 없는 작업입니다."


@pytest.mark.parametrize("who", ["ym", "boss"])
@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/projects/1/members", None),
    ("get", "/api/projects/1/members/available-users", None),
    ("post", "/api/projects/1/members", {"user_id": 1, "role": "admin"}),
    ("put", "/api/projects/1/members/1", {"role": "tester"}),
    ("delete", "/api/projects/1/members/1", None),
])
def test_전체_범위_키로도_멤버_관리는_못_한다(env, who, method, path, body):
    """관리자는 모든 프로젝트의 admin 이라, 관리자 키로 프로젝트마다 멤버를 추가하면 일괄 배정을
    막아도 아무 계정을 전 프로젝트 admin 으로 올릴 수 있었다(QA 2인 지적)."""
    client, db = env
    raw = _new_key(client, _session(client, who), scope="full")["key"]
    kw = {"headers": _bearer(raw)}
    if body is not None:
        kw["json"] = body
    r = getattr(client, method)(path, **kw)
    assert (r.status_code, r.json()["detail"]) == (403, "API 키로는 할 수 없는 작업입니다. 로그인해서 진행해 주세요."), r.text
    db.expire_all()
    assert db.query(ProjectMember).count() == 1


def test_멤버_관리는_세션으로는_된다(env):
    client, db = env
    h = _session(client)
    assert client.get("/api/projects/1/members", headers=h).status_code == 200
    assert client.get("/api/projects/1/members/available-users", headers=h).status_code == 200
    r = client.post("/api/projects/1/members", headers=h, json={"user_id": 1, "role": "tester"})
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    assert client.put(f"/api/projects/1/members/{mid}", headers=h, json={"role": "admin"}).status_code == 200
    assert client.delete(f"/api/projects/1/members/{mid}", headers=h).status_code == 204


@pytest.mark.parametrize("who", ["ym", "boss"])
def test_키로는_공개_범위를_바꾸지_못한다(env, who):
    """관리자 키로 프로젝트마다 공개로 바꾸면 비멤버 전원에게 열리고 키를 폐기해도 남는다(QA1 지적)."""
    client, db = env
    h = _bearer(_new_key(client, _session(client, who), scope="full")["key"])
    r = client.put("/api/projects/1", headers=h, json={"is_private": False})
    assert (r.status_code, r.json()["detail"]) == (403, "API 키로는 할 수 없는 작업입니다. 로그인해서 진행해 주세요.")
    db.expire_all()
    assert db.query(Project).get(1).is_private is True
    # 다른 칸은 키로도 고친다. 같은 값을 다시 보내는 것도 막지 않는다
    r = client.put("/api/projects/1", headers=h, json={"name": "P2", "is_private": True})
    assert r.status_code == 200, r.text


def test_공개_범위는_세션으로는_바꾼다(env):
    client, db = env
    r = client.put("/api/projects/1", headers=_session(client), json={"is_private": False})
    assert r.status_code == 200 and r.json()["is_private"] is False



def test_키로는_공개_프로젝트를_만들지_못한다(env):
    """관리자 키로 남의 비공개 TC 를 내보내 공개 프로젝트에 가져오면 공개 전환과 같다(QA1 지적)."""
    client, db = env
    h = _bearer(_new_key(client, _session(client, "boss"), scope="full")["key"])
    before = db.query(Project).count()
    for body in ({"name": "copy"}, {"name": "copy", "is_private": False}):
        r = client.post("/api/projects", headers=h, json=body)
        assert (r.status_code, r.json()["detail"]) == (403, "API 키로는 공개 프로젝트를 만들 수 없습니다. is_private 를 true 로 보내거나 로그인해서 진행해 주세요."), r.text
    db.expire_all()
    assert db.query(Project).count() == before
    r = client.post("/api/projects", headers=h, json={"name": "copy", "is_private": True})
    assert r.status_code == 201 and r.json()["is_private"] is True
    # 세션은 공개로 만든다
    r = client.post("/api/projects", headers=_session(client), json={"name": "open"})
    assert r.status_code == 201 and r.json()["is_private"] is False
