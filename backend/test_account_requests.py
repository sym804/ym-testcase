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
