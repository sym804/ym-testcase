"""리포트 응답의 비율 기준

`pass_rate` 만 분모가 수행분(pass+fail+block)이고 나머지 넷은 전체다. 이름만으로는
어느 쪽인지 알 수 없어서, 다섯을 더하면 100 이 되리라 기대하게 된다.

분모를 응답에 드러낸다. 그러면 소비자가 어느 기준인지 보고 쓸 수 있다.
비율 정의 자체는 바꾸지 않는다. `pass_rate` 를 전체 기준으로 되돌리면 미수행이
많은 수행에서 합격률이 실제보다 낮게 보이던 SYM-57 로 돌아간다.

실행: cd backend && TEST_PORT=8099 TEST_BASE_URL=http://127.0.0.1:8099 python -m pytest test_report_contract.py -v
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
def run_with_mixed_results(token):
    """TC 4건 중 2건 PASS, 1건 FAIL, 1건은 미수행으로 남긴 수행."""
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__report_rate__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                  json={"name": "기본", "parent_id": None, "is_folder": False})

    ids = []
    for i in (1, 2, 3, 4):
        rr = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=h, json={
            "no": i, "tc_id": f"TC-R-{i}", "category": "기본", "test_steps": "1. 실행",
            "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
        })
        assert rr.status_code == 201, rr.text
        ids.append(rr.json()["id"])

    rn = requests.post(f"{BASE}/api/projects/{pid}/testruns", headers=h,
                       json={"name": "비율 확인", "round": 1})
    assert rn.status_code == 201, rn.text
    run_id = rn.json()["id"]

    payload = [
        {"test_case_id": ids[0], "result": "PASS"},
        {"test_case_id": ids[1], "result": "PASS"},
        {"test_case_id": ids[2], "result": "FAIL"},
    ]
    sub = requests.post(f"{BASE}/api/projects/{pid}/testruns/{run_id}/results",
                        headers=h, json=payload)
    assert sub.status_code in (200, 201), sub.text

    yield pid, run_id
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _summary(token, pid, run_id):
    r = requests.get(f"{BASE}/api/projects/{pid}/reports?run_id={run_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()["summary"]


def test_수행분_분모를_응답에_드러낸다(token, run_with_mixed_results):
    """pass_rate 의 분모를 소비자가 알 수 있어야 한다."""
    pid, run_id = run_with_mixed_results
    s = _summary(token, pid, run_id)

    assert "executed" in s, f"분모를 알 수 없다: {sorted(s)}"
    assert s["executed"] == 3, f"pass+fail+block 이어야 한다: {s}"
    assert s["total"] == 4


def test_합격률은_수행분_기준이다(token, run_with_mixed_results):
    """미수행을 분모에 넣으면 합격률이 실제보다 낮게 보인다(SYM-57)."""
    pid, run_id = run_with_mixed_results
    s = _summary(token, pid, run_id)

    assert s["pass_rate"] == 66.7, f"2/3 이어야 한다: {s}"


def test_나머지_비율은_전체_기준이다(token, run_with_mixed_results):
    """기준이 다르다는 사실 자체를 테스트로 못박는다."""
    pid, run_id = run_with_mixed_results
    s = _summary(token, pid, run_id)

    assert s["fail_rate"] == 25.0, f"1/4 이어야 한다: {s}"
    assert s["not_started_rate"] == 25.0, f"1/4 이어야 한다: {s}"
