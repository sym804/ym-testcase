"""동시에 복제해도 같은 시트에서 번호가 겹치지 않는다.

max(no) 를 읽고 +1 해서 넣으면 두 요청이 같은 값을 읽는 창이 생긴다. `no` 에
유니크 제약이 없어 DB 도 막아 주지 않는다.

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_tc_clone_concurrent.py -v
"""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

import dev_db_guard

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


#: 동시에 보낼 복제 요청 수. 늘릴수록 겹칠 확률이 오르지만 그만큼 느려진다.
FANOUT = 8


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture
def seeded(token):
    """한 시트에 TC 한 건. 이것을 여러 번 동시에 복제한다."""
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__clone_race__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    rs = requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                       json={"name": "결제", "parent_id": None, "is_folder": False})
    assert rs.status_code in (200, 201), rs.text

    rt = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=h, json={
        "no": 1, "tc_id": "TC-결제-001", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "결제", "priority": "High",
    })
    assert rt.status_code == 201, rt.text

    yield pid, rt.json()["id"]
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _nos(token, pid, sheet):
    r = requests.get(f"{BASE}/api/projects/{pid}/testcases",
                     headers=auth(token), params={"sheet_name": sheet})
    assert r.status_code == 200, r.text
    return sorted(tc["no"] for tc in r.json())


def test_concurrent_clone_gives_distinct_numbers(token, seeded):
    pid, tc_id = seeded
    h = auth(token)

    def clone(_):
        return requests.post(f"{BASE}/api/projects/{pid}/testcases/{tc_id}/clone", headers=h)

    with ThreadPoolExecutor(max_workers=FANOUT) as pool:
        responses = list(pool.map(clone, range(FANOUT)))

    created = [r.json()["no"] for r in responses if r.status_code == 201]
    assert created, f"복제가 한 건도 성공하지 않았다: {[r.status_code for r in responses]}"

    nos = _nos(token, pid, "결제")
    assert len(nos) == len(set(nos)), f"같은 시트에 같은 번호가 둘 이상이다: {nos}"
    # 원본 1 건 + 성공한 복제만큼. 번호가 1 부터 빈틈없이 이어져야 한다.
    assert nos == list(range(1, len(nos) + 1)), f"번호가 이어지지 않는다: {nos}"


def test_concurrent_bulk_clone_gives_distinct_numbers(token, seeded):
    pid, tc_id = seeded
    h = auth(token)

    def bulk(_):
        return requests.post(f"{BASE}/api/projects/{pid}/testcases/bulk-clone",
                             headers=h, json={"ids": [tc_id]})

    with ThreadPoolExecutor(max_workers=FANOUT) as pool:
        responses = list(pool.map(bulk, range(FANOUT)))

    assert any(r.status_code == 201 for r in responses), \
        f"복제가 한 건도 성공하지 않았다: {[r.status_code for r in responses]}"

    nos = _nos(token, pid, "결제")
    assert len(nos) == len(set(nos)), f"같은 시트에 같은 번호가 둘 이상이다: {nos}"
