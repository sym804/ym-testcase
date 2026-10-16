"""시트 복사: 같은 프로젝트 안에서 시트 하나를 TC 와 함께 통째로 복제한다.

- 새 시트는 같은 부모 아래, 원본 바로 다음 자리에 '<원본> (복사)' 로 생긴다.
- 살아 있는 TC 만 원본 순서대로 들어가고 번호는 1 부터 이어진다.
- TC ID 는 프로젝트 전체에서 유일해야 하므로 TC 복제와 같은 '-copy' 규칙으로 새로 받는다.
- 수행 결과, 변경 이력, 첨부는 복사하지 않는다. 진행 중인 전체 범위 수행에는 NS 로 흡수된다.
"""
import requests

from auth_helpers import bearer, login, make_user
from models import ProjectMember, ProjectRole, TestCase, TestCaseSheet, TestResult, UserRole


def _api(env, h):
    def call(method, path, **kw):
        return requests.request(method, env.base + path, headers=h, **kw)
    return call


def _project_with_sheet(env, *, username="owner"):
    uid = make_user(env.Session, username=username, role=UserRole.user)
    h = bearer(login(env.base, username))
    api = _api(env, h)
    pid = api("POST", "/api/projects", json={"name": "P-" + username}).json()["id"]
    return uid, h, api, pid


def _sheet(api, pid, name, parent_id=None, is_folder=False):
    r = api("POST", f"/api/projects/{pid}/testcases/sheets",
            json={"name": name, "parent_id": parent_id, "is_folder": is_folder})
    assert r.status_code == 200, r.text
    return r.json()


def _tc(api, pid, sheet, tc_id, **fields):
    r = api("POST", f"/api/projects/{pid}/testcases",
            json={"tc_id": tc_id, "sheet_name": sheet, "test_steps": "s-" + tc_id, **fields})
    assert r.status_code == 201, r.text
    return r.json()


def _live_tcs(env, pid, sheet):
    with env.Session() as s:
        return (s.query(TestCase)
                .filter(TestCase.project_id == pid, TestCase.sheet_name == sheet, TestCase.deleted_at.is_(None))
                .order_by(TestCase.no).all())


def test_시트를_복사하면_살아_있는_TC_가_순서대로_새_번호와_새_ID_로_들어간다(auth_env):
    uid, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "로그인")
    a = _tc(api, pid, "로그인", "TC-1", category="인증", priority="높음",
            precondition="없음", expected_result="성공", custom_fields={"os": "iOS"})
    gone = _tc(api, pid, "로그인", "TC-2")
    _tc(api, pid, "로그인", "TC-3")
    assert api("DELETE", f"/api/projects/{pid}/testcases/{gone['id']}").status_code in (200, 204)

    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["name"] == "로그인 (복사)"
    assert body["tc_count"] == 2
    assert body["is_folder"] is False

    copied = _live_tcs(auth_env, pid, "로그인 (복사)")
    assert [(t.no, t.tc_id) for t in copied] == [(1, "TC-1-copy"), (2, "TC-3-copy")]
    first = copied[0]
    assert (first.category, first.priority, first.precondition, first.expected_result, first.test_steps) == \
        ("인증", "높음", "없음", "성공", "s-TC-1")
    assert first.custom_fields == {"os": "iOS"}
    assert first.created_by == uid
    assert first.id != a["id"]

    # 원본은 그대로
    assert [t.tc_id for t in _live_tcs(auth_env, pid, "로그인")] == ["TC-1", "TC-3"]


def test_복사본은_같은_부모_아래_원본_바로_다음_자리에_생긴다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    folder = _sheet(api, pid, "웹", is_folder=True)
    s1 = _sheet(api, pid, "A", parent_id=folder["id"])
    _sheet(api, pid, "B", parent_id=folder["id"])
    _sheet(api, pid, "C", parent_id=folder["id"])

    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{s1['id']}/copy")
    assert r.status_code == 201, r.text
    assert r.json()["parent_id"] == folder["id"]

    tree = api("GET", f"/api/projects/{pid}/testcases/sheets").json()
    web = next(n for n in tree if n["id"] == folder["id"])
    ordered = sorted(web["children"], key=lambda n: (n["sort_order"], n["id"]))
    assert [n["name"] for n in ordered] == ["A", "A (복사)", "B", "C"]


def test_이름이_겹치면_비어_있는_다음_번호를_붙인다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "결제")
    _sheet(api, pid, "결제 (복사)")
    _tc(api, pid, "결제", "PAY-1")

    r1 = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r1.status_code == 201, r1.text
    assert r1.json()["name"] == "결제 (복사 2)"
    r2 = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r2.json()["name"] == "결제 (복사 3)"
    # 같은 원본을 두 번 복사해도 TC ID 가 겹치지 않는다
    assert [t.tc_id for t in _live_tcs(auth_env, pid, "결제 (복사 3)")] == ["PAY-1-copy-2"]


def test_긴_이름은_100자_안으로_자른다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    long_name = "가" * 100
    src = _sheet(api, pid, long_name)
    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    name = r.json()["name"]
    assert len(name) <= 100
    assert name.endswith(" (복사)")


def test_TC_ID_가_50자_상한에_닿아도_복사된다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "긴ID")
    _tc(api, pid, "긴ID", "X" * 50)
    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    copied = _live_tcs(auth_env, pid, "긴ID (복사)")
    # 50자를 넘으면 뒤를 잘라 '-copy' 가 사라지고, 원본과 겹치므로 '-2' 가 붙는다(TC 복제와 같은 규칙)
    assert [t.tc_id for t in copied] == ["X" * 48 + "-2"]


def test_빈_시트도_복사된다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "빈 시트")
    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    assert r.json()["tc_count"] == 0
    with auth_env.Session() as s:
        assert s.query(TestCaseSheet).filter_by(project_id=pid, name="빈 시트 (복사)").count() == 1


def test_폴더는_복사하지_않는다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    folder = _sheet(api, pid, "모바일", is_folder=True)
    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{folder['id']}/copy")
    assert r.status_code == 400


def test_다른_프로젝트의_시트_id_는_404(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    other_pid = api("POST", "/api/projects", json={"name": "다른"}).json()["id"]
    other_sheet = _sheet(api, other_pid, "남의 시트")
    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{other_sheet['id']}/copy")
    assert r.status_code == 404


def test_프로젝트_admin_이_아니면_복사할_수_없다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "권한")
    tester = make_user(auth_env.Session, username="tester1", role=UserRole.user)
    with auth_env.Session() as s:
        s.add(ProjectMember(project_id=pid, user_id=tester, role=ProjectRole.tester))
        s.commit()
    h_t = bearer(login(auth_env.base, "tester1"))
    r = requests.post(auth_env.base + f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy", headers=h_t)
    assert r.status_code == 403
    with auth_env.Session() as s:
        assert s.query(TestCaseSheet).filter_by(project_id=pid).count() == 1


def test_진행_중인_전체_범위_수행에는_NS_로_들어가고_다른_시트_범위_수행에는_안_들어간다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "회원")
    _tc(api, pid, "회원", "MEM-1")
    _tc(api, pid, "회원", "MEM-2")
    full = api("POST", f"/api/projects/{pid}/testruns", json={"name": "전체"})
    assert full.status_code == 201, full.text
    scoped = api("POST", f"/api/projects/{pid}/testruns", json={"name": "회원만", "sheet_names": ["회원"]})
    assert scoped.status_code == 201, scoped.text

    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    copied_ids = {t.id for t in _live_tcs(auth_env, pid, "회원 (복사)")}
    assert len(copied_ids) == 2  # 비어 있으면 아래 all() 이 그냥 통과한다

    with auth_env.Session() as s:
        in_full = {x.test_case_id: x.result.value for x in
                   s.query(TestResult).filter(TestResult.test_run_id == full.json()["id"]).all()}
        in_scoped = {x.test_case_id for x in
                     s.query(TestResult).filter(TestResult.test_run_id == scoped.json()["id"]).all()}
    assert all(in_full.get(i) == "NS" for i in copied_ids)
    assert not (copied_ids & in_scoped)


def test_시트_행_없이_살아_있는_TC_가_쓰는_이름은_건너뛴다(auth_env):
    """지운 시트의 TC 를 복원하면 시트 행 없이 그 이름을 쓰는 TC 가 남는다.
    그 이름으로 복사본을 만들면 남의 TC 와 섞여 번호도 이어 붙는다."""
    uid, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "주문")
    _tc(api, pid, "주문", "ORD-1")
    with auth_env.Session() as s:
        s.add(TestCase(project_id=pid, no=1, tc_id="LEFT-1", sheet_name="주문 (복사)", created_by=uid))
        s.commit()

    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "주문 (복사 2)"
    assert [(t.no, t.tc_id) for t in _live_tcs(auth_env, pid, "주문 (복사 2)")] == [(1, "ORD-1-copy")]
    assert [t.tc_id for t in _live_tcs(auth_env, pid, "주문 (복사)")] == ["LEFT-1"]


def test_수행_동기화가_실패하면_복사가_통째로_취소된다(auth_env, monkeypatch):
    """복사를 커밋한 뒤 동기화가 실패하면 복사본은 남는데 화면은 실패로 보이고, 다시 누르면 하나 더 생긴다."""
    from services import run_sync_service

    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "배송")
    _tc(api, pid, "배송", "SHIP-1")

    real_sync = run_sync_service.sync_project_in_progress_runs
    seen = {}

    def boom(*a, **k):
        # 실제 동기화를 커밋 없이 돌린 뒤 실패시킨다. commit=False 를 빼면 여기서 커밋되어 복사본이 남는다.
        seen["commit"] = k.get("commit", True)
        real_sync(*a, **k)
        raise RuntimeError("sync failed")
    monkeypatch.setattr(run_sync_service, "sync_project_in_progress_runs", boom)

    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 500
    with auth_env.Session() as s:
        assert s.query(TestCaseSheet).filter_by(project_id=pid, name="배송 (복사)").count() == 0
        assert s.query(TestCase).filter_by(project_id=pid, sheet_name="배송 (복사)").count() == 0
        assert s.query(TestCaseSheet).filter_by(project_id=pid).count() == 1
    assert seen == {"commit": False}


def test_원본의_수행_결과는_복사본에_따라가지_않는다(auth_env):
    _, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "검색")
    tc = _tc(api, pid, "검색", "SR-1")
    run = api("POST", f"/api/projects/{pid}/testruns", json={"name": "검색만", "sheet_names": ["검색"]}).json()
    r = api("POST", f"/api/projects/{pid}/testruns/{run['id']}/results",
            json=[{"test_case_id": tc["id"], "result": "FAIL", "actual_result": "깨짐"}])
    assert r.status_code == 200, r.text

    assert api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy").status_code == 201
    copied = _live_tcs(auth_env, pid, "검색 (복사)")
    assert len(copied) == 1
    with auth_env.Session() as s:
        assert s.query(TestResult).filter(TestResult.test_case_id == copied[0].id).count() == 0
        assert s.query(TestResult).filter(TestResult.test_case_id == tc["id"]).one().result.value == "FAIL"


def test_TC_가_많은_시트도_번호가_빈틈없이_이어진다(auth_env):
    uid, h, api, pid = _project_with_sheet(auth_env)
    src = _sheet(api, pid, "대량")
    with auth_env.Session() as s:
        s.add_all([TestCase(project_id=pid, no=i, tc_id=f"BULK-{i}", sheet_name="대량", created_by=uid)
                   for i in range(1, 301)])
        s.commit()
    r = api("POST", f"/api/projects/{pid}/testcases/sheets/{src['id']}/copy")
    assert r.status_code == 201, r.text
    copied = _live_tcs(auth_env, pid, "대량 (복사)")
    assert [t.no for t in copied] == list(range(1, 301))
    assert copied[0].tc_id == "BULK-1-copy" and copied[-1].tc_id == "BULK-300-copy"


def test_루트_시트도_원본_바로_다음_자리에_생긴다(auth_env):
    """부모가 없는 시트는 parent_id IS NULL 로 형제를 찾는다. '= NULL' 로 비교하면 아무도 안 밀린다."""
    _, h, api, pid = _project_with_sheet(auth_env)
    a = _sheet(api, pid, "A")
    _sheet(api, pid, "B")
    _sheet(api, pid, "C")
    assert api("POST", f"/api/projects/{pid}/testcases/sheets/{a['id']}/copy").status_code == 201

    tree = api("GET", f"/api/projects/{pid}/testcases/sheets").json()
    ordered = sorted(tree, key=lambda n: (n["sort_order"], n["id"]))
    assert [n["name"] for n in ordered] == ["A", "A (복사)", "B", "C"]
