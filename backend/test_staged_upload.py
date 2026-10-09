"""스테이징 업로드: 주소 발급 -> 클라이언트가 직접 올림 -> 처리 요청이 upload_id 로 꺼내 씀.

Vercel 함수는 요청 본문을 4.5MB 까지만 받는다. 큰 파일은 저장소에 직접 올리고 함수는
upload_id 만 받는다. 로컬은 발급 주소가 백엔드 자신이라 흐름이 같다.

실행: cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_staged_upload.py -q
"""
import os

import pytest
import requests
from fastapi import HTTPException

import dev_db_guard

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def _login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


@pytest.fixture(scope="module")
def admin():
    return _login("admin", ADMIN_PW)


@pytest.fixture(scope="module")
def other(admin):
    requests.post(f"{BASE}/api/auth/register", json={
        "email": "__staged_other__@example.com", "password": "other12345", "display_name": "Other"})
    return _login("__staged_other__@example.com", "other12345")


def _stage(h, purpose="tc_import", size=5, filename="tcs.xlsx"):
    return requests.post(f"{BASE}/api/uploads", headers=h, json={
        "purpose": purpose, "filename": filename, "size": size, "content_type": "application/octet-stream"})


def _put(target, data):
    url = target["url"] if target["url"].startswith("http") else BASE + target["url"]
    return requests.request(target["method"], url, data=data, headers=target["headers"])


def _db():
    from database import SessionLocal
    return SessionLocal()


def _user(db, username):
    from models import User
    return db.query(User).filter(User.username == username).one()


def test_발급_올림_꺼내기_왕복(admin):
    from services.staged_upload import consume

    r = _stage(admin)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["method"] == "PUT" and t["upload_id"]
    assert _put(t, b"hello").status_code == 200
    db = _db()
    try:
        name, _, data = consume(db, t["upload_id"], _user(db, "admin"), "tc_import")
        db.commit()
    finally:
        db.close()
    assert (name, data) == ("tcs.xlsx", b"hello")


def test_다른_사용자의_업로드는_꺼낼_수_없다(admin, other):
    from services.staged_upload import consume

    t = _stage(admin).json()
    _put(t, b"hello")
    db = _db()
    try:
        with pytest.raises(HTTPException) as e:
            consume(db, t["upload_id"], _user(db, "__staged_other__@example.com"), "tc_import")
        assert e.value.status_code == 403
    finally:
        db.close()


def test_목적이_다르면_400_두_번_꺼내면_409(admin):
    from services.staged_upload import consume

    t = _stage(admin).json()
    _put(t, b"hello")
    db = _db()
    try:
        me = _user(db, "admin")
        with pytest.raises(HTTPException) as e:
            consume(db, t["upload_id"], me, "result_import")
        assert e.value.status_code == 400
        consume(db, t["upload_id"], me, "tc_import")
        db.commit()
        with pytest.raises(HTTPException) as e:
            consume(db, t["upload_id"], me, "tc_import")
        assert e.value.status_code == 409
    finally:
        db.close()


def test_선언보다_크게_올려도_상한에서_막힌다(admin, monkeypatch):
    """선언 크기는 작게, 실제로는 상한보다 크게 올리면 올리는 단계에서 413."""
    from services import staged_upload

    monkeypatch.setitem(staged_upload.PURPOSE_LIMITS, "tc_import", 8)
    t = _stage(admin, size=3).json()
    assert _put(t, b"x" * 9).status_code == 413


def test_상한을_넘는_선언은_발급하지_않는다(admin):
    r = _stage(admin, purpose="tc_import", size=10 * 1024 * 1024 + 1)
    assert r.status_code == 413


def test_모르는_목적은_400(admin):
    assert _stage(admin, purpose="avatar").status_code == 400


def test_토큰이_틀리면_401_같은_업로드에_두_번_올리면_409(admin):
    t = _stage(admin).json()
    bad = dict(t, url=t["url"].split("?")[0] + "?token=forged")
    assert _put(bad, b"hello").status_code == 401
    assert _put(t, b"hello").status_code == 200
    assert _put(t, b"again").status_code == 409


def test_다른_업로드의_토큰으로는_올릴_수_없다(admin):
    a = _stage(admin).json()
    b = _stage(admin).json()
    crossed = dict(a, url=a["url"].split("?")[0] + "?" + b["url"].split("?")[1])
    assert _put(crossed, b"hello").status_code == 401


def test_로그인_없이_발급할_수_없다():
    assert _stage({}).status_code == 401
