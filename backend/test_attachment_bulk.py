"""런 단위 첨부 일괄 조회 테스트

첨부를 행마다 따로 부르면 화면에 들어온 시점에는 첨부 유무를 알 수 없어,
그 셀을 눌러 보기 전까지 첨부가 없는 것처럼 보였다(SYM-36).

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_attachment_bulk.py -v
"""
import io
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
def run_with_attachment(token):
    """TC 2건짜리 런을 만들고, 첫 결과 행에만 첨부를 단다."""
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__att_bulk__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    for i in (1, 2):
        rc = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=h, json={
            "no": i, "tc_id": f"TC-ATT-{i:03d}", "category": "첨부", "test_steps": "1. 실행",
            "expected_result": "성공", "sheet_name": "기본",
        })
        assert rc.status_code == 201, rc.text

    rr = requests.post(f"{BASE}/api/projects/{pid}/testruns", headers=h, json={"name": "첨부 런", "round": 1})
    assert rr.status_code == 201, rr.text
    run_id = rr.json()["id"]

    detail = requests.get(f"{BASE}/api/projects/{pid}/testruns/{run_id}", headers=h)
    assert detail.status_code == 200, detail.text
    results = detail.json()["results"]
    assert len(results) == 2, results
    target = results[0]["id"]

    up = requests.post(
        f"{BASE}/api/attachments/{target}", headers=h,
        files={"file": ("증거.png", io.BytesIO(b"fake-png-bytes"), "image/png")},
    )
    assert up.status_code == 200, up.text

    yield {"project_id": pid, "run_id": run_id, "result_id": target,
           "attachment_id": up.json()["id"], "results": results}

    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def test_런_첨부를_한_번에_조회한다(token, run_with_attachment):
    """행마다 부르지 않아도 런 전체의 첨부를 받을 수 있어야 한다."""
    ctx = run_with_attachment
    r = requests.get(f"{BASE}/api/attachments/by-run/{ctx['run_id']}", headers=auth(token))
    assert r.status_code == 200, r.text
    atts = r.json()
    assert len(atts) == 1
    assert atts[0]["id"] == ctx["attachment_id"]
    assert atts[0]["test_result_id"] == ctx["result_id"]
    assert atts[0]["filename"] == "증거.png"


def test_다른_런의_첨부는_섞이지_않는다(token, run_with_attachment):
    """런 경계를 넘어 첨부가 새면 다른 회차의 증거가 이번 회차로 보인다."""
    ctx = run_with_attachment
    h = auth(token)
    other = requests.post(f"{BASE}/api/projects/{ctx['project_id']}/testruns",
                          headers=h, json={"name": "다른 런", "round": 2})
    assert other.status_code == 201, other.text

    r = requests.get(f"{BASE}/api/attachments/by-run/{other.json()['id']}", headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_없는_런은_404(token):
    r = requests.get(f"{BASE}/api/attachments/by-run/99999999", headers=auth(token))
    assert r.status_code == 404, r.text


def test_인증_없이는_거부된다(run_with_attachment):
    r = requests.get(f"{BASE}/api/attachments/by-run/{run_with_attachment['run_id']}")
    assert r.status_code in (401, 403), r.text
