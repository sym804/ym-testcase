"""프로젝트 잠금은 번호를 건드리는 요청만 잡고, 무한정 기다리지 않는다.

셀 하나를 고치는 자동 저장(PUT, 시트 이동 없음)까지 잠그면, 같은 프로젝트에서 엑셀
가져오기가 도는 동안 모든 셀 저장이 줄을 서고 실패하면 입력이 되돌아간다(QA2 지적).
번호를 건드리는 요청은 잠금을 기다리되, 오래 걸리면 409 로 다시 시도하라고 알린다.

실행: cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_lock_scope.py -q
"""
import os

import pytest
import requests
from sqlalchemy import create_engine, text

import dev_db_guard

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def seeded(token):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__lock_scope__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    for name in ("A", "B"):
        rs = requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                           json={"name": name, "parent_id": None, "is_folder": False})
        assert rs.status_code in (200, 201), rs.text
    rt = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=h, json={
        "tc_id": "TC-LOCK-1", "test_steps": "1", "expected_result": "2", "sheet_name": "A",
    })
    assert rt.status_code == 201, rt.text
    yield pid, rt.json()["id"]
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


@pytest.fixture
def held_project_lock():
    """다른 연결이 프로젝트 잠금을 쥐고 있는 상태를 만든다. 테스트가 끝나면 푼다."""
    eng = create_engine(os.environ["DATABASE_URL"])
    conn = eng.connect()
    tx = conn.begin()

    def hold(pid):
        conn.execute(text("SELECT pg_advisory_xact_lock(1, :p)"), {"p": pid})

    yield hold
    tx.rollback()
    conn.close()
    eng.dispose()


def test_시트_이동_없는_수정은_잠금을_기다리지_않는다(token, seeded, held_project_lock):
    pid, tcid = seeded
    held_project_lock(pid)
    r = requests.put(f"{BASE}/api/projects/{pid}/testcases/{tcid}", headers=auth(token),
                     json={"test_steps": "바뀐 단계"}, timeout=5)
    assert r.status_code == 200, r.text


def test_번호를_건드리는_요청은_오래_기다리지_않고_409(token, seeded, held_project_lock, monkeypatch):
    pid, tcid = seeded
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "300")
    held_project_lock(pid)
    r = requests.put(f"{BASE}/api/projects/{pid}/testcases/{tcid}", headers=auth(token),
                     json={"sheet_name": "B"}, timeout=5)
    assert r.status_code == 409, r.text
    assert "다른 작업" in r.json()["detail"]
