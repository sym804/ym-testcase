"""시트를 골라 만드는 테스트 수행

런은 프로젝트 전체 TC 를 담았고 시트를 고를 수 없었다(SYM-37).
고른 범위는 런에 저장되어, 새 TC 가 생겨도 그 범위 밖은 흡수하지 않아야 한다.

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_run_sheet_scope.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

if BASE.endswith(":8008") and os.getenv("ALLOW_DEV_DB") != "1":
    pytest.skip(
        "개발 서버(8008)의 실 DB 오염 방지를 위해 건너뜀. "
        "격리 실행: TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 pytest test_run_sheet_scope.py",
        allow_module_level=True,
    )


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _add_tc(token, pid, no, tc_id, sheet):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json={
        "no": no, "tc_id": tc_id, "category": sheet, "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": sheet, "priority": "High",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def project(token):
    """시트 셋에 TC 2건씩."""
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__run_scope__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    for sheet in ("로그인", "결제", "마이페이지"):
        rs = requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                           json={"name": sheet, "parent_id": None, "is_folder": False})
        assert rs.status_code in (200, 201), rs.text

    no = 1
    for sheet in ("로그인", "결제", "마이페이지"):
        for i in (1, 2):
            _add_tc(token, pid, no, f"TC-{sheet}-{i:03d}", sheet)
            no += 1

    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _sheets_of(token, pid, run_id):
    r = requests.get(f"{BASE}/api/projects/{pid}/testruns/{run_id}", headers=auth(token))
    assert r.status_code == 200, r.text
    return sorted({res["test_case"]["sheet_name"] for res in r.json()["results"]})


def test_시트를_고르면_그_시트의_TC만_담는다(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "결제만", "round": 1, "sheet_names": ["결제"]})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["sheet_names"] == ["결제"]

    detail = requests.get(f"{BASE}/api/projects/{project}/testruns/{run['id']}", headers=auth(token))
    assert len(detail.json()["results"]) == 2
    assert _sheets_of(token, project, run["id"]) == ["결제"]


def test_시트를_안_고르면_전체를_담는다(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "전체", "round": 1})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["sheet_names"] is None
    assert _sheets_of(token, project, run["id"]) == ["결제", "로그인", "마이페이지"]


def test_범위_밖에_TC가_생겨도_런에_들어오지_않는다(token, project):
    """★런의 범위를 저장하지 않으면 여기서 제외한 시트가 통째로 들어온다."""
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "로그인만", "round": 1, "sheet_names": ["로그인"]})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]
    assert len(_sheets_of(token, project, run_id)) == 1

    _add_tc(token, project, 100, "TC-결제-999", "결제")
    _add_tc(token, project, 101, "TC-로그인-999", "로그인")

    detail = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=auth(token))
    tc_ids = sorted(res["test_case"]["tc_id"] for res in detail.json()["results"])
    assert "TC-로그인-999" in tc_ids, "범위 안의 새 TC 는 흡수해야 한다"
    assert "TC-결제-999" not in tc_ids, "범위 밖의 TC 가 들어왔다"
    assert _sheets_of(token, project, run_id) == ["로그인"]


def test_복제하면_범위도_따라간다(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "원본", "round": 1, "sheet_names": ["마이페이지"]})
    assert r.status_code == 201, r.text
    src_id = r.json()["id"]

    c = requests.post(f"{BASE}/api/projects/{project}/testruns/{src_id}/clone", headers=auth(token))
    assert c.status_code in (200, 201), c.text
    assert c.json()["sheet_names"] == ["마이페이지"]
    assert _sheets_of(token, project, c.json()["id"]) == ["마이페이지"]


def test_없는_시트는_400(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "오타", "round": 1, "sheet_names": ["없는시트"]})
    assert r.status_code == 400, r.text


def test_빈_목록은_400(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "빈목록", "round": 1, "sheet_names": []})
    assert r.status_code == 400, r.text


def test_범위_밖_TC의_결과는_제출할_수_없다(token, project):
    """★결과 제출은 프로젝트 소속만 봤다. 그대로 두면 범위 밖 TC 가 런에 들어온다."""
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "로그인 범위", "round": 1, "sheet_names": ["로그인"]})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]

    tcs = requests.get(f"{BASE}/api/projects/{project}/testcases", headers=auth(token)).json()
    outside = next(tc for tc in tcs if tc["sheet_name"] == "결제")
    inside = next(tc for tc in tcs if tc["sheet_name"] == "로그인")

    bad = requests.post(f"{BASE}/api/projects/{project}/testruns/{run_id}/results", headers=auth(token),
                        json=[{"test_case_id": outside["id"], "result": "PASS"}])
    assert bad.status_code == 400, bad.text

    ok = requests.post(f"{BASE}/api/projects/{project}/testruns/{run_id}/results", headers=auth(token),
                       json=[{"test_case_id": inside["id"], "result": "PASS"}])
    assert ok.status_code == 200, ok.text
    assert _sheets_of(token, project, run_id) == ["로그인"]


def test_폴더는_런_범위로_고를_수_없다(token, project):
    h = auth(token)
    f = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                      json={"name": "모바일", "parent_id": None, "is_folder": True})
    assert f.status_code in (200, 201), f.text

    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=h,
                      json={"name": "폴더", "round": 1, "sheet_names": ["모바일"]})
    assert r.status_code == 400, r.text


def test_중복_시트명은_한_번만_저장된다(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=auth(token),
                      json={"name": "중복", "round": 1, "sheet_names": ["결제", "결제", "결제"]})
    assert r.status_code == 201, r.text
    assert r.json()["sheet_names"] == ["결제"]


def test_대시보드_분모가_런_범위를_따른다(token, project):
    """★분모를 프로젝트 전체 TC 로 잡으면 범위 런을 다 수행해도 진행률이 안 찬다.

    실측(수정 전): 결제 시트 2건을 전부 PASS 했는데 total 6, not_started 4, pass_rate 33.3.
    """
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=h,
                      json={"name": "대시보드 범위", "round": 1, "sheet_names": ["결제"]})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]

    detail = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=h).json()
    payload = [{"test_case_id": res["test_case_id"], "result": "PASS"} for res in detail["results"]]
    assert len(payload) == 2
    sub = requests.post(f"{BASE}/api/projects/{project}/testruns/{run_id}/results", headers=h, json=payload)
    assert sub.status_code == 200, sub.text

    summary = requests.get(f"{BASE}/api/projects/{project}/dashboard/summary?run_id={run_id}", headers=h).json()
    assert summary["total"] == 2, summary
    assert summary["pass"] == 2, summary
    assert summary["not_started"] == 0, summary
    assert summary["pass_rate"] == 100.0, summary

    cat = requests.get(f"{BASE}/api/projects/{project}/dashboard/category?run_id={run_id}", headers=h).json()
    assert sum(c["total"] for c in cat) == 2, cat
    assert sum(c["not_started"] for c in cat) == 0, cat

    pri = requests.get(f"{BASE}/api/projects/{project}/dashboard/priority?run_id={run_id}", headers=h).json()
    assert sum(x["total"] for x in pri) == 2, pri


def test_시트_이름을_바꿔도_런_범위가_따라간다(token, project):
    """★런 범위는 시트 이름으로 저장된다. 이름이 바뀌면 그 범위가 아무것도 가리키지 않는다.

    그러면 결과 제출이 전부 400 이 되고, 새 TC 도 흡수되지 않으며, 시트 탭도 사라진다.
    """
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=h,
                      json={"name": "이름변경 전", "round": 1, "sheet_names": ["결제"]})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]

    sheets = requests.get(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h).json()
    def find(nodes):
        for n in nodes:
            if n["name"] == "결제":
                return n
            got = find(n.get("children") or [])
            if got:
                return got
    target = find(sheets)
    assert target, sheets

    rn = requests.put(f"{BASE}/api/projects/{project}/testcases/sheets/{target['id']}/rename",
                      headers=h, json={"new_name": "결제하기"})
    assert rn.status_code == 200, rn.text

    run = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=h).json()
    assert run["sheet_names"] == ["결제하기"], run["sheet_names"]

    # 결과 제출이 막히지 않아야 한다
    tc_id = run["results"][0]["test_case_id"]
    sub = requests.post(f"{BASE}/api/projects/{project}/testruns/{run_id}/results", headers=h,
                        json=[{"test_case_id": tc_id, "result": "PASS"}])
    assert sub.status_code == 200, sub.text

    # 바뀐 이름의 시트에 TC 를 더하면 흡수해야 한다
    _add_tc(token, project, 200, "TC-결제하기-NEW", "결제하기")
    after = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=h).json()
    assert "TC-결제하기-NEW" in {x["test_case"]["tc_id"] for x in after["results"]}


def test_삭제된_TC의_결과는_대시보드_분자에서_빠진다(token, project):
    """★분모는 활성 TC 로 좁혔는데 분자가 결과 행 전체면 pass 가 total 을 넘는다."""
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/testruns", headers=h,
                      json={"name": "삭제 포함", "round": 1, "sheet_names": ["마이페이지"]})
    assert r.status_code == 201, r.text
    run_id = r.json()["id"]

    detail = requests.get(f"{BASE}/api/projects/{project}/testruns/{run_id}", headers=h).json()
    payload = [{"test_case_id": x["test_case_id"], "result": "PASS"} for x in detail["results"]]
    requests.post(f"{BASE}/api/projects/{project}/testruns/{run_id}/results", headers=h, json=payload)

    victim = detail["results"][0]["test_case_id"]
    d = requests.delete(f"{BASE}/api/projects/{project}/testcases/{victim}", headers=h)
    assert d.status_code in (200, 204), d.text

    summary = requests.get(f"{BASE}/api/projects/{project}/dashboard/summary?run_id={run_id}", headers=h).json()
    assert summary["pass"] <= summary["total"], summary
    assert summary["total"] == len(payload) - 1, summary
    assert summary["not_started"] >= 0, summary
