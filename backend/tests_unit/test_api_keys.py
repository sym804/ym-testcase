"""API 키

- 발급 원문은 한 번만, 목록에는 해시도 원문도 없다.
- 키로 인증하면 키 주인으로 동작하고 프로젝트 권한도 그대로다.
- 폐기 · 만료 · 틀린 비밀은 401. 어느 단계에서 막혔는지는 같은 문구.
- 키로는 키 관리 · 비밀번호 변경 · 로그아웃 · 관리자 초기화 · 복구 승인을 못 한다.
- 비밀번호가 바뀌면(본인 · 관리자 초기화) 그 사용자의 키가 모두 폐기된다.

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
from models import ApiKey, Project, User, UserRole, now_kst

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
    db.add(Project(name="P", created_by=user.id, is_private=True))
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


def _new_key(client, h, name="CI", days=90):
    r = client.post("/api/auth/api-keys", json={"name": name, "expires_days": days}, headers=h)
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
