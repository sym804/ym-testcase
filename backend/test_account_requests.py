"""계정 복구 (아이디 찾기 / 비밀번호 재설정) 통합 테스트

실행: cd backend && python -m pytest test_account_requests.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")


@pytest.fixture(autouse=True)
def _reset_submit_limit():
    """접수 제한은 IP 기준 1시간 10회다. 테스트가 같은 IP 로 그 예산을 나눠 쓰면
    뒤쪽 테스트가 429 로 죽는다. 프로덕션 한도는 그대로 두고 테스트만 격리한다."""
    try:
        from routes.account_requests import _submit_hits
        _submit_hits.clear()
    except ImportError:
        pass
    yield


def test_account_request_model_exists():
    from models import AccountRequest, AccountRequestStatus, AccountRequestType

    assert AccountRequest.__tablename__ == "account_requests"
    assert AccountRequestType.find_id.value == "find_id"
    assert AccountRequestType.reset_password.value == "reset_password"
    assert AccountRequestStatus.pending.value == "pending"
    assert AccountRequestStatus.approved.value == "approved"
    assert AccountRequestStatus.rejected.value == "rejected"
    assert AccountRequestStatus.completed.value == "completed"


def test_account_request_columns():
    from models import AccountRequest

    cols = {c.name for c in AccountRequest.__table__.columns}
    assert cols == {
        "id", "request_type", "status",
        "claimed_username", "claimed_display_name", "contact", "note",
        "user_id", "code_hash", "code_expires_at",
        "created_at", "resolved_at", "resolved_by_id",
    }


def _submit(payload):
    return requests.post(f"{BASE}/api/auth/account-requests", json=payload)


def test_submit_reset_request_for_existing_user():
    r = _submit({
        "request_type": "reset_password",
        "claimed_username": "admin",
        "contact": "사내 메신저 admin",
    })
    assert r.status_code == 201, r.text
    assert r.json() == {"message": "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."}


def test_submit_reset_request_for_missing_user_is_indistinguishable():
    """계정 열거 방지: 없는 아이디로 요청해도 응답이 동일해야 한다."""
    r = _submit({
        "request_type": "reset_password",
        "claimed_username": "__no_such_user__",
        "contact": "사내 메신저 nobody",
    })
    assert r.status_code == 201, r.text
    assert r.json() == {"message": "요청이 접수되었습니다. 관리자 확인 후 연락드립니다."}


def test_submit_find_id_request():
    r = _submit({
        "request_type": "find_id",
        "claimed_display_name": "Admin",
        "contact": "사내 메신저 admin",
    })
    assert r.status_code == 201, r.text


def test_reset_request_without_username_is_rejected():
    r = _submit({"request_type": "reset_password", "contact": "x"})
    assert r.status_code == 422, r.text


def test_find_id_request_without_display_name_is_rejected():
    r = _submit({"request_type": "find_id", "contact": "x"})
    assert r.status_code == 422, r.text


def _login(username, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def admin_headers():
    return _login("admin", os.getenv("TEST_ADMIN_PASSWORD", "test1234"))


@pytest.fixture(scope="module")
def normal_user(admin_headers):
    """일반 사용자 하나를 만들어 둔다. 비밀번호를 바꾸는 테스트의 대상이 된다."""
    requests.post(f"{BASE}/api/auth/register", json={
        "username": "__recover_user__", "password": "origin1234", "display_name": "Recover User",
    })
    r = requests.get(f"{BASE}/api/auth/users", headers=admin_headers)
    uid = next(u["id"] for u in r.json() if u["username"] == "__recover_user__")
    return {"username": "__recover_user__", "id": uid}


def test_list_requires_admin(normal_user):
    h = _login("__recover_user__", "origin1234")
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=h)
    assert r.status_code == 403, r.text


def test_admin_can_list_pending(admin_headers):
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    assert all("code_hash" not in item for item in body)


def test_approve_find_id_returns_username_and_no_code(admin_headers, normal_user):
    _submit({
        "request_type": "find_id",
        "claimed_display_name": "Recover User",
        "contact": "메신저 recover",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json()
               if x["request_type"] == "find_id" and x["claimed_display_name"] == "Recover User")

    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": normal_user["id"]}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "__recover_user__"
    assert body["code"] is None


def test_approve_reset_returns_plaintext_code_once(admin_headers, normal_user):
    _submit({
        "request_type": "reset_password",
        "claimed_username": "__recover_user__",
        "contact": "메신저 recover",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json()
               if x["request_type"] == "reset_password"
               and x["claimed_username"] == "__recover_user__")

    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": normal_user["id"]}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["code"] and len(body["code"]) >= 12
    assert body["code_expires_at"]

    # 목록에는 코드가 다시 나오지 않는다
    r2 = requests.get(f"{BASE}/api/auth/account-requests",
                      params={"status": "approved"}, headers=admin_headers)
    item = next(x for x in r2.json() if x["id"] == req["id"])
    assert "code" not in item and "code_hash" not in item


def test_approve_twice_conflicts(admin_headers, normal_user):
    _submit({
        "request_type": "find_id",
        "claimed_display_name": "Dup Target",
        "contact": "메신저 dup",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json() if x["claimed_display_name"] == "Dup Target")
    url = f"{BASE}/api/auth/account-requests/{req['id']}/approve"
    assert requests.post(url, json={"user_id": normal_user["id"]}, headers=admin_headers).status_code == 200
    assert requests.post(url, json={"user_id": normal_user["id"]}, headers=admin_headers).status_code == 409


def test_duplicate_pending_is_not_created(admin_headers):
    """같은 대상으로 두 번 요청해도 큐에는 하나만 쌓인다."""
    target = "__dup_pending__"
    for _ in range(2):
        r = _submit({
            "request_type": "reset_password",
            "claimed_username": target,
            "contact": "메신저 dup-pending",
        })
        assert r.status_code == 201, r.text

    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    same = [x for x in r.json()
            if x["request_type"] == "reset_password" and x["claimed_username"] == target]
    assert len(same) == 1, f"pending 이 {len(same)}건 쌓였다"


def test_approve_requires_admin(normal_user):
    """승인도 관리자 전용이다. 목록만 막고 승인을 열어두면 의미가 없다."""
    _submit({
        "request_type": "find_id",
        "claimed_display_name": "Forbidden Target",
        "contact": "메신저 forbidden",
    })
    h = _login("__recover_user__", "origin1234")
    r = requests.post(
        f"{BASE}/api/auth/account-requests/1/approve",
        json={"user_id": normal_user["id"]}, headers=h,
    )
    assert r.status_code == 403, r.text


def test_code_is_stored_hashed_not_plaintext(admin_headers, normal_user):
    """승인 응답의 평문 코드가 DB 에 그대로 들어가면 안 된다."""
    from database import SessionLocal
    from models import AccountRequest

    _submit({
        "request_type": "reset_password",
        "claimed_username": "__hash_check__",
        "contact": "메신저 hash",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json() if x["claimed_username"] == "__hash_check__")
    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": normal_user["id"]}, headers=admin_headers,
    )
    code = r.json()["code"]

    db = SessionLocal()
    try:
        row = db.query(AccountRequest).filter(AccountRequest.id == req["id"]).first()
        assert row.code_hash, "코드 해시가 비어 있다"
        assert row.code_hash != code, "평문 코드가 그대로 저장되었다"
        assert row.code_hash.startswith("$2"), "bcrypt 해시가 아니다"
    finally:
        db.close()


def test_reject_moves_to_rejected(admin_headers):
    _submit({
        "request_type": "reset_password",
        "claimed_username": "__no_such_user__",
        "contact": "메신저 nobody",
    })
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json() if x["claimed_username"] == "__no_such_user__")

    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/reject",
        json={"note": "존재하지 않는 계정"}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text

    r = requests.get(f"{BASE}/api/auth/account-requests",
                     params={"status": "rejected"}, headers=admin_headers)
    item = next(x for x in r.json() if x["id"] == req["id"])
    assert item["status"] == "rejected"
    assert item["note"] == "존재하지 않는 계정"


def _issue_code(admin_headers, username, user_id, contact="메신저 code"):
    """대상 계정에 대해 재설정 코드를 발급받는다."""
    _submit({"request_type": "reset_password", "claimed_username": username, "contact": contact})
    r = requests.get(f"{BASE}/api/auth/account-requests", headers=admin_headers)
    req = next(x for x in r.json()
               if x["request_type"] == "reset_password" and x["claimed_username"] == username)
    r = requests.post(
        f"{BASE}/api/auth/account-requests/{req['id']}/approve",
        json={"user_id": user_id}, headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    return req["id"], r.json()["code"]


def test_reset_with_code_changes_password(admin_headers, normal_user):
    _, code = _issue_code(admin_headers, normal_user["username"], normal_user["id"])

    r = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "changed1234",
    })
    assert r.status_code == 200, r.text

    try:
        # 새 비밀번호로 로그인된다
        ok = requests.post(f"{BASE}/api/auth/login", json={
            "username": normal_user["username"], "password": "changed1234",
        })
        assert ok.status_code == 200, ok.text

        # 옛 비밀번호는 실패한다
        ng = requests.post(f"{BASE}/api/auth/login", json={
            "username": normal_user["username"], "password": "origin1234",
        })
        assert ng.status_code == 401
    finally:
        # 위 assert 가 실패해도 계정을 origin1234 로 되돌려야 한다(테스트 데이터 원복 규칙)
        _, code2 = _issue_code(admin_headers, normal_user["username"], normal_user["id"])
        back = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
            "username": normal_user["username"], "code": code2, "new_password": "origin1234",
        })
        assert back.status_code == 200, back.text


def test_code_cannot_be_reused(admin_headers, normal_user):
    req_id, code = _issue_code(admin_headers, normal_user["username"], normal_user["id"])
    first = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "origin1234",
    })
    assert first.status_code == 200, first.text

    # status 필터가 아니라 code_hash 자체가 지워졌는지 직접 확인한다.
    # status 필터만으로 재사용이 막힌다면, code_hash 를 지우는 코드가 회귀해도
    # 아래 401 재사용 검증만으로는 잡히지 않는다.
    from database import SessionLocal
    from models import AccountRequest

    db = SessionLocal()
    try:
        row = db.query(AccountRequest).filter(AccountRequest.id == req_id).first()
        assert row.code_hash is None, "코드 해시가 남아 있다. 재사용 방어가 status 필터에만 의존한다"
        assert row.status.value == "completed"
    finally:
        db.close()

    again = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "origin1234",
    })
    assert again.status_code == 401


def test_expired_code_fails(admin_headers, normal_user):
    """만료 시각을 과거로 돌려 검증한다."""
    from datetime import timedelta

    from database import SessionLocal
    from models import AccountRequest, now_kst

    req_id, code = _issue_code(admin_headers, normal_user["username"], normal_user["id"])

    db = SessionLocal()
    try:
        req = db.query(AccountRequest).filter(AccountRequest.id == req_id).first()
        req.code_expires_at = now_kst() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
        "username": normal_user["username"], "code": code, "new_password": "origin1234",
    })
    assert r.status_code == 401


def test_wrong_code_is_rate_limited(admin_headers):
    """틀린 코드를 반복하면 429. 다른 테스트의 계정과 키가 겹치지 않도록 전용 계정을 쓴다."""
    requests.post(f"{BASE}/api/auth/register", json={
        "username": "__rl_target__", "password": "origin1234", "display_name": "RL Target",
    })
    saw_429 = False
    for _ in range(12):
        r = requests.post(f"{BASE}/api/auth/reset-password/verify", json={
            "username": "__rl_target__", "code": "wrongwrongwrong", "new_password": "origin1234",
        })
        if r.status_code == 429:
            saw_429 = True
            break
        assert r.status_code == 401
    assert saw_429
