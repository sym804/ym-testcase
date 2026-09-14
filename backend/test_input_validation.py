"""입력 검증 - 만들 때는 막고 고칠 때는 통과하던 자리

같은 값을 생성에서는 거부하는데 수정에서는 받아 주면, 검증이 있다는 사실이
오히려 잘못된 안심을 준다. 커스텀 필드 타입이 그랬다(생성 400, 수정 200).

실행: cd backend && TEST_PORT=8099 TEST_BASE_URL=http://127.0.0.1:8099 python -m pytest test_input_validation.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

import dev_db_guard

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture
def project(token):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__validation__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                  json={"name": "기본", "parent_id": None, "is_folder": False})
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _add_tc(token, pid, no=1, tc_id="TC-001"):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json={
        "no": no, "tc_id": tc_id, "category": "기본", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── 커스텀 필드 ───────────────────────────────────────────────────────────────

def test_커스텀필드_수정도_타입을_검증한다(token, project):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/custom-fields", headers=h,
                      json={"field_name": "환경", "field_type": "text"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    bad = requests.put(f"{BASE}/api/projects/{project}/custom-fields/{fid}", headers=h,
                       json={"field_type": "EVIL_TYPE"})
    assert bad.status_code == 400, f"수정으로 임의 타입이 저장됐다: {bad.status_code} {bad.text}"

    still = requests.get(f"{BASE}/api/projects/{project}/custom-fields", headers=h)
    assert still.json()[0]["field_type"] == "text"


def test_커스텀필드_수정은_허용된_타입을_받는다(token, project):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/custom-fields", headers=h,
                      json={"field_name": "환경2", "field_type": "text"})
    fid = r.json()["id"]

    ok = requests.put(f"{BASE}/api/projects/{project}/custom-fields/{fid}", headers=h,
                      json={"field_type": "select", "options": ["A", "B"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["field_type"] == "select"


# ── 벌크 삭제 ─────────────────────────────────────────────────────────────────

def test_벌크삭제의_잘못된_ids는_400이다(token, project):
    """숫자가 아닌 값이 오면 500 이 아니라 400 이어야 한다."""
    r = requests.delete(f"{BASE}/api/projects/{project}/testcases/bulk?ids=abc",
                        headers=auth(token))
    assert r.status_code == 400, f"서버 오류로 샜다: {r.status_code} {r.text}"


def test_벌크삭제는_정상_ids를_처리한다(token, project):
    tc1 = _add_tc(token, project, 1, "TC-B01")
    tc2 = _add_tc(token, project, 2, "TC-B02")

    r = requests.delete(f"{BASE}/api/projects/{project}/testcases/bulk?ids={tc1},{tc2}",
                        headers=auth(token))
    assert r.status_code == 200, r.text


# ── 삭제된 TC ─────────────────────────────────────────────────────────────────

def test_삭제된_TC는_수정할_수_없다(token, project):
    """지운 TC 를 고칠 수 있으면 삭제와 복원의 의미가 흔들린다."""
    tc = _add_tc(token, project, 1, "TC-D01")
    d = requests.delete(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=auth(token))
    assert d.status_code in (200, 204), d.text

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=auth(token),
                     json={"category": "바뀐값"})
    assert r.status_code == 404, f"삭제된 TC 가 수정됐다: {r.status_code} {r.text}"


def test_살아있는_TC는_수정할_수_있다(token, project):
    tc = _add_tc(token, project, 1, "TC-D02")
    r = requests.put(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=auth(token),
                     json={"category": "바뀐값"})
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "바뀐값"
