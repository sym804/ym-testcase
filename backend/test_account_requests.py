"""계정 복구 (아이디 찾기 / 비밀번호 재설정) 통합 테스트

실행: cd backend && python -m pytest test_account_requests.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")


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
