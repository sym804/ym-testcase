"""런 생성 이후 추가된 TC의 런 동기화 테스트

진행 중인 런은 조회 시 누락 TC의 결과 행(NS)을 자동 생성하고,
완료된 런은 스냅샷을 그대로 유지해야 한다.

실행: cd backend && python -m pytest test_run_tc_sync.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://localhost:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

# 이 테스트는 프로젝트와 TC를 실제로 만든다. 개발 서버(8008)는 사용자의 실 DB를 쓰므로
# 거기에 붙으면 테스트 데이터가 실 데이터에 섞인다. conftest는 포트가 이미 점유돼 있으면
# 격리 DB 없이 그 서버를 그대로 쓰기 때문에 경고만으로는 막지 못한다.
# 격리 포트를 명시하거나(TEST_PORT/TEST_BASE_URL), 의도적으로 허용해야 실행된다.
if BASE.endswith(":8008") and os.getenv("ALLOW_DEV_DB") != "1":
    pytest.skip(
        "개발 서버(8008)의 실 DB 오염 방지를 위해 건너뜀. "
        "격리 실행: TEST_PORT=8009 TEST_BASE_URL=http://localhost:8009 pytest test_run_tc_sync.py",
        allow_module_level=True,
    )


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
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__run_sync__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def make_sheet(token, pid, name):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=auth(token), json={"name": name})
    assert r.status_code in (200, 201), r.text


def make_tc(token, pid, no, tc_id, sheet="기본"):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json={
        "no": no, "tc_id": tc_id, "test_steps": "s", "expected_result": "e", "sheet_name": sheet,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def make_run(token, pid, name="R1"):
    r = requests.post(f"{BASE}/api/projects/{pid}/testruns", headers=auth(token), json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def run_tc_ids(token, pid, run_id):
    r = requests.get(f"{BASE}/api/projects/{pid}/testruns/{run_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return {res["test_case_id"] for res in r.json()["results"]}


def test_in_progress_run_picks_up_tc_added_later(token, project):
    """진행 중 런: 런 생성 후 추가된 TC가 조회 시 결과 행으로 채워진다"""
    tc1 = make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)
    assert run_tc_ids(token, project, run_id) == {tc1}

    # 런 생성 이후에 새 시트를 만들고 TC를 추가한 상황 (실제 발생한 시나리오)
    make_sheet(token, project, "공통")
    tc2 = make_tc(token, project, 2, "TC-002", sheet="공통")

    assert run_tc_ids(token, project, run_id) == {tc1, tc2}


def test_synced_result_is_not_started(token, project):
    """자동 생성된 결과 행은 미입력(NS) 상태여야 한다"""
    make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)
    tc2 = make_tc(token, project, 2, "TC-002")

    r = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=auth(token))
    added = next(res for res in r.json()["results"] if res["test_case_id"] == tc2)
    assert added["result"] == "NS"


def test_completed_run_keeps_snapshot(token, project):
    """완료된 런: 이후 추가된 TC를 흡수하지 않고 스냅샷을 유지한다"""
    tc1 = make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)

    r = requests.put(f"{BASE}/api/projects/{project}/testruns/{run_id}/complete", headers=auth(token))
    assert r.status_code == 200, r.text

    make_tc(token, project, 2, "TC-002")

    assert run_tc_ids(token, project, run_id) == {tc1}


def test_already_deleted_tc_is_not_synced(token, project):
    """이미 삭제된 TC는 런에 끌어들이지 않는다"""
    tc1 = make_tc(token, project, 1, "TC-001")
    tc2 = make_tc(token, project, 2, "TC-002")

    r = requests.delete(f"{BASE}/api/projects/{project}/testcases/{tc2}", headers=auth(token))
    assert r.status_code == 204, r.text

    run_id = make_run(token, project)

    assert run_tc_ids(token, project, run_id) == {tc1}


def test_tc_deleted_after_joining_run_keeps_its_row(token, project):
    """런에 들어간 뒤 삭제된 TC의 결과 행은 남는다 (기존 동작 유지)

    이 앱은 런에 포함된 TC가 삭제돼도 결과 행을 지우지 않는다. 완료된 런의
    스냅샷을 보존하기 위해서다. 진행 중 런도 같은 규칙을 따른다.
    """
    tc1 = make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)
    tc2 = make_tc(token, project, 2, "TC-002")
    assert run_tc_ids(token, project, run_id) == {tc1, tc2}

    r = requests.delete(f"{BASE}/api/projects/{project}/testcases/{tc2}", headers=auth(token))
    assert r.status_code == 204, r.text

    assert run_tc_ids(token, project, run_id) == {tc1, tc2}


def test_report_matches_run_without_opening_it(token, project):
    """런 상세를 열지 않아도 리포트가 새 TC를 포함해야 한다

    상세 조회 시점에만 동기화하면, 런을 열기 전과 후의 리포트 숫자가 달라진다.
    리포트의 total은 test_results 실제 행 수라 동기화 누락이 그대로 드러난다.
    """
    make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)
    make_tc(token, project, 2, "TC-002")

    # 런 상세(GET /testruns/{id})를 한 번도 호출하지 않은 상태에서 리포트 조회
    r = requests.get(
        f"{BASE}/api/projects/{project}/reports",
        headers=auth(token), params={"run_id": run_id},
    )
    assert r.status_code == 200, r.text
    summary = r.json()["summary"]

    assert summary["total"] == 2, f"리포트가 런 생성 이후 추가된 TC를 누락함: {summary}"
    assert summary["not_started"] == 2, summary


def test_synced_rows_keep_no_order(token, project):
    """런에 나중에 편입된 TC도 TC 번호 순서로 보여야 한다

    결과 행은 편입 순서로 저장되므로, 기존 TC 사이에 끼는 번호로 추가하면
    정렬을 걸지 않는 한 화면에서 맨 뒤로 밀린다.
    """
    make_tc(token, project, 1, "TC-A")
    make_tc(token, project, 3, "TC-C")
    run_id = make_run(token, project)

    make_tc(token, project, 2, "TC-B")  # 기존 TC 사이에 끼는 번호

    r = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=auth(token))
    order = [res["test_case"]["no"] for res in r.json()["results"]]
    assert order == sorted(order), f"결과 행이 TC 번호 순이 아님: {order}"


def test_reopen_absorbs_tc_added_while_completed(token, project):
    """완료 기간에 추가된 TC는 reopen 시점에 흡수된다

    reopen 후 상세를 열지 않고 바로 완료해도 누락되지 않아야 한다.
    """
    tc1 = make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)
    requests.put(f"{BASE}/api/projects/{project}/testruns/{run_id}/complete", headers=auth(token))

    # 완료 상태에서 추가 -> 스냅샷이므로 흡수되지 않아야 한다
    tc2 = make_tc(token, project, 2, "TC-002")
    assert run_tc_ids(token, project, run_id) == {tc1}

    r = requests.put(f"{BASE}/api/projects/{project}/testruns/{run_id}/reopen", headers=auth(token))
    assert r.status_code == 200, r.text

    # 상세 조회 없이도 리포트에 반영돼야 한다
    summary = requests.get(
        f"{BASE}/api/projects/{project}/reports", headers=auth(token), params={"run_id": run_id},
    ).json()["summary"]
    assert summary["total"] == 2, f"reopen 시 누락 TC가 흡수되지 않음: {summary}"
    assert run_tc_ids(token, project, run_id) == {tc1, tc2}


def test_run_with_no_results_is_still_returned(token, project):
    """TC가 하나도 없는 프로젝트의 런도 정상 조회된다

    결과 정렬을 위해 join을 걸었으므로, 결과 0건인 런이 join에서 탈락하지 않아야 한다.
    """
    run_id = make_run(token, project)  # TC 없이 런 생성

    r = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["results"] == []


def test_sync_is_idempotent(token, project):
    """반복 조회해도 결과 행이 중복 생성되지 않는다"""
    make_tc(token, project, 1, "TC-001")
    run_id = make_run(token, project)
    make_tc(token, project, 2, "TC-002")

    first = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=auth(token)).json()
    second = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=auth(token)).json()

    assert len(first["results"]) == 2
    assert len(second["results"]) == 2
    assert {r["id"] for r in first["results"]} == {r["id"] for r in second["results"]}
