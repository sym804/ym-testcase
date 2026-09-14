"""집계 일관성 - 삭제된 TC 와 런 소속

대시보드 전체 모드가 분모만 좁히고 분자는 결과 행 전체를 세어, TC 를 지우면
합격률이 부풀려졌다(실측 36.4% -> 40.0%). 같은 함수의 run_id 분기에는 그 필터가
있었고 여섯 집계 중 이 한 곳만 빠져 있었다.

리포트와 런 상세는 반대로 삭제된 TC 의 결과를 계속 세서, 같은 런인데 화면마다
총계가 달랐다(실측 리포트 4 / 대시보드 3).

기준은 화면의 질문을 따른다. 대시보드는 "지금 몇 건이 남았나" 라서 지운 TC 를
분모와 분자 양쪽에서 뺀다. 리포트와 런 상세는 "그때 몇 건을 수행했나" 라서 지워진
TC 의 결과도 그대로 센다. 두 수가 달라지는 것이 정상이다.

보존하기로 한 기록이 사라지지 않도록 `purge_service` 가 수행에 편입된 TC 를
완전 삭제에서 뺀다(tests_unit/test_purge_keeps_run_history.py). 지운 TC 에 새
결과를 제출하는 것은 막는다. 어느 기준으로도 의미가 없는 데이터가 된다.

실행: cd backend && TEST_PORT=8099 TEST_BASE_URL=http://127.0.0.1:8099 python -m pytest test_aggregation_consistency.py -v
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


def _make_project(token, name):
    r = requests.post(f"{BASE}/api/projects", headers=auth(token), json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _add_tc(token, pid, no, tc_id):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json={
        "no": no, "tc_id": tc_id, "category": "기본", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def project(token):
    """TC 3건짜리 프로젝트. 정리까지 한다."""
    h = auth(token)
    pid = _make_project(token, "__agg_main__")
    requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                  json={"name": "기본", "parent_id": None, "is_folder": False})
    ids = [_add_tc(token, pid, i, f"TC-AGG-{i:03d}") for i in (1, 2, 3)]
    yield pid, ids
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _run_with_all_pass(token, pid, tc_ids):
    """TC 전부를 PASS 로 채운 런을 만든다."""
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{pid}/testruns", headers=h,
                      json={"name": "집계런", "round": 1})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    payload = [{"test_case_id": tc, "result": "PASS"} for tc in tc_ids]
    rr = requests.post(f"{BASE}/api/projects/{pid}/testruns/{run_id}/results",
                       headers=h, json=payload)
    assert rr.status_code in (200, 201), rr.text
    return run_id


def _summary(token, pid, run_id=None):
    url = f"{BASE}/api/projects/{pid}/dashboard/summary"
    if run_id is not None:
        url += f"?run_id={run_id}"
    r = requests.get(url, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def test_삭제된_TC의_PASS는_전체모드_분자에서도_빠진다(token, project):
    """분모만 줄고 분자가 남으면 합격률이 부풀려진다."""
    pid, ids = project
    _run_with_all_pass(token, pid, ids)

    before = _summary(token, pid)
    assert before["total"] == 3 and before["pass"] == 3

    r = requests.delete(f"{BASE}/api/projects/{pid}/testcases/{ids[0]}", headers=auth(token))
    assert r.status_code in (200, 204), r.text

    after = _summary(token, pid)
    assert after["total"] == 2, "삭제한 TC 는 분모에서 빠져야 한다"
    assert after["pass"] == 2, f"삭제한 TC 의 PASS 가 분자에 남았다: {after}"
    assert after["pass_rate"] == 100.0, f"합격률이 부풀려졌다: {after}"


def test_대시보드는_다른_프로젝트의_런을_집계하지_않는다(token, project):
    """run_id 만 보고 프로젝트를 안 보면 남의 집계가 새어 나온다."""
    pid, ids = project
    other = _make_project(token, "__agg_other__")
    try:
        requests.post(f"{BASE}/api/projects/{other}/testcases/sheets", headers=auth(token),
                      json={"name": "기본", "parent_id": None, "is_folder": False})
        other_ids = [_add_tc(token, other, i, f"TC-OTH-{i:03d}") for i in (1, 2)]
        other_run = _run_with_all_pass(token, other, other_ids)

        got = _summary(token, pid, run_id=other_run)
        assert got["pass"] == 0, f"다른 프로젝트 런의 집계가 새어 나왔다: {got}"
    finally:
        requests.delete(f"{BASE}/api/projects/{other}", headers=auth(token))


def test_리포트는_지운_TC의_수행_기록을_보존한다(token, project):
    """리포트는 "그때 몇 건을 수행했나" 다. 대시보드와 기준이 다른 것이 의도다.

    대시보드는 "지금 몇 건이 남았나" 를 묻는 화면이라 지운 TC 를 뺀다. 두 수가
    달라지는 것이 정상이고, 같아야 한다고 묶으면 한쪽의 질문에 답할 수 없게 된다.
    """
    pid, ids = project
    run_id = _run_with_all_pass(token, pid, ids)

    r = requests.delete(f"{BASE}/api/projects/{pid}/testcases/{ids[0]}", headers=auth(token))
    assert r.status_code in (200, 204), r.text

    rep = requests.get(f"{BASE}/api/projects/{pid}/reports?run_id={run_id}", headers=auth(token))
    assert rep.status_code == 200, rep.text
    rep_summary = rep.json()["summary"]
    assert rep_summary["total"] == 3, f"수행 기록이 줄었다: {rep_summary}"
    assert rep_summary["pass"] == 3, f"수행 기록이 줄었다: {rep_summary}"

    dash = _summary(token, pid, run_id=run_id)
    assert dash["total"] == 2, f"대시보드는 지운 TC 를 빼야 한다: {dash}"
    assert dash["pass"] == 2, f"대시보드는 지운 TC 를 빼야 한다: {dash}"


def test_런에_없던_남의_TC는_결과를_제출할_수_없다(token, project):
    """제출 한 번으로 런의 범위가 늘어나면 안 된다.

    진행 중 런은 같은 프로젝트의 새 TC 를 자동으로 흡수하므로, 런에 결과 행이
    없는 TC 는 사실상 남의 프로젝트 것뿐이다. 그 경로를 막는지 본다.
    """
    pid, _ = project
    other = _make_project(token, "__agg_outsider__")
    try:
        requests.post(f"{BASE}/api/projects/{other}/testcases/sheets", headers=auth(token),
                      json={"name": "기본", "parent_id": None, "is_folder": False})
        stranger = _add_tc(token, other, 1, "TC-OUT-001")
        run_id = _run_with_all_pass(token, pid, [])

        rr = requests.post(f"{BASE}/api/projects/{pid}/testruns/{run_id}/results",
                           headers=auth(token),
                           json=[{"test_case_id": stranger, "result": "FAIL"}])
        assert rr.status_code == 400, (
            f"남의 프로젝트 TC 가 런에 끼어들었다: {rr.status_code} {rr.text}"
        )
    finally:
        requests.delete(f"{BASE}/api/projects/{other}", headers=auth(token))


def test_런에_이미_있는_행은_TC를_지워도_결과를_저장할_수_있다(token, project):
    """★그리드에 보이는 행은 저장도 돼야 한다.

    런 상세는 "그때의 기록" 이라 지워진 TC 의 결과 행을 그대로 보여 준다.
    그런데 저장만 막으면 사라지지도 채워지지도 않는 행이 남는다. 게다가 결과
    제출은 여러 행을 한 배열로 보내므로, 그런 행이 하나 섞이면 배치 전체가
    거절되어 같이 입력한 멀쩡한 행까지 날아간다.
    """
    pid, ids = project
    run_id = _run_with_all_pass(token, pid, ids)

    r = requests.delete(f"{BASE}/api/projects/{pid}/testcases/{ids[0]}", headers=auth(token))
    assert r.status_code in (200, 204), r.text

    rr = requests.post(f"{BASE}/api/projects/{pid}/testruns/{run_id}/results", headers=auth(token),
                       json=[{"test_case_id": ids[0], "result": "FAIL"}])
    assert rr.status_code == 200, (
        f"런에 보이는 행인데 저장이 거부됐다: {rr.status_code} {rr.text}"
    )


def test_지운_행이_섞여도_같은_배치의_다른_행은_저장된다(token, project):
    """한 행 때문에 배치 전체가 거절되면 같이 입력한 값이 날아간다."""
    pid, ids = project
    run_id = _run_with_all_pass(token, pid, ids)

    r = requests.delete(f"{BASE}/api/projects/{pid}/testcases/{ids[0]}", headers=auth(token))
    assert r.status_code in (200, 204), r.text

    rr = requests.post(f"{BASE}/api/projects/{pid}/testruns/{run_id}/results", headers=auth(token),
                       json=[
                           {"test_case_id": ids[0], "result": "FAIL"},
                           {"test_case_id": ids[1], "result": "BLOCK"},
                       ])
    assert rr.status_code == 200, f"배치가 통째로 거절됐다: {rr.status_code} {rr.text}"

    detail = requests.get(f"{BASE}/api/projects/{pid}/testruns/{run_id}", headers=auth(token))
    saved = {x["test_case_id"]: x["result"] for x in detail.json()["results"]}
    assert saved.get(ids[1]) == "BLOCK", f"멀쩡한 행이 저장되지 않았다: {saved}"
