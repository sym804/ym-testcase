"""종료된 테스트 수행의 TC 내용 고정

결과 행은 TC 를 test_case_id 로만 가리켜서, 수행을 종료한 뒤 TC 를 고치면 그 수행의
화면, 엑셀, 리포트가 고친 내용으로 바뀌었다. 이미 실행한 TC 라서 종료된 수행은 그때
내용으로 남아야 한다. 진행 중인 수행은 지금 TC 를 보여 준다(사용자 결정 2026-11-06).

실행: cd backend && python -m pytest tests_unit/test_run_tc_snapshot.py -q
"""
import asyncio
import importlib.util
import io
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from models import (
    Project, RunIssue, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun,
    TestRunStatus, User,
)
from routes.reports import (
    _category_summary_sql, _comparison, _issue_items, _priority_summary_sql, _run_issues,
)
from routes.run_issues import _resolve_test_cases
from routes.testruns import complete_testrun, export_testrun_excel, get_testrun, reopen_testrun
from schemas import TestResultResponse, TestRunResponse
from services.tc_snapshot import SNAPSHOT_FIELDS, FrozenCase, snapshot_of

OLD = dict(tc_id="T-1", category="로그인", priority="높음", test_steps="1. 열기",
           expected_result="열린다", precondition="계정 있음", sheet_name="S")
NEW = dict(tc_id="T-1b", category="인증", priority="낮음", test_steps="1. 닫기",
           expected_result="닫힌다", precondition="없음", sheet_name="S2")


@pytest.fixture
def env(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    s = Session()
    u = User(username="u", password_hash="x", display_name="U", role="admin")
    s.add(u)
    s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p)
    s.flush()
    s.add_all([TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False),
               TestCaseSheet(project_id=p.id, name="S2", sort_order=1, is_folder=False)])
    tc = TestCase(project_id=p.id, no=1, created_by=u.id, **OLD)
    s.add(tc)
    run = TestRun(project_id=p.id, name="R", round=1, created_by=u.id)
    s.add(run)
    s.flush()
    s.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=TestResultValue.FAIL,
                     actual_result="안 열림", executed_by=u.id))
    s.commit()
    yield s, p, run, tc, u
    s.close()


def _edit(s, tc, values):
    for k, v in values.items():
        setattr(tc, k, v)
    s.commit()


def _shown(s, p, run, u) -> dict:
    """수행 상세 API 가 내보내는 첫 결과의 TC 칸."""
    s.expire_all()
    body = TestRunResponse.model_validate(get_testrun(p.id, run.id, db=s, current_user=u)).model_dump()
    return body["results"][0]["test_case"]


#: 고정 대상인 내용 칸. 시트는 위치라서 고정하지 않는다(tc_snapshot.py).
CONTENT = [k for k in OLD if k != "sheet_name"]


def _pick(d, keys=CONTENT):
    return {k: d[k] for k in keys}


# ── 핵심 규칙 ────────────────────────────────────────────

def test_종료된_수행은_TC_를_고쳐도_종료_시점_내용을_보여_준다(env):
    s, p, run, tc, u = env
    complete_testrun(p.id, run.id, db=s, current_user=u)

    _edit(s, tc, NEW)

    assert _pick(_shown(s, p, run, u)) == _pick(OLD)


def test_진행_중인_수행은_고친_TC_를_바로_보여_준다(env):
    s, p, run, tc, u = env

    _edit(s, tc, NEW)

    assert _pick(_shown(s, p, run, u)) == _pick(NEW)


def test_다시_열면_지금_TC_를_보여_주고_다시_종료하면_그때_내용으로_고정한다(env):
    s, p, run, tc, u = env
    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, NEW)

    reopen_testrun(p.id, run.id, db=s, current_user=u)
    assert _pick(_shown(s, p, run, u)) == _pick(NEW)
    # 고정을 풀면 SQL 로도 NULL 이다. JSON null 로 남으면 IS NULL 이 거짓이라 고정으로 읽힌다.
    assert s.execute(text("SELECT count(*) FROM test_results WHERE tc_snapshot IS NULL")).scalar() == 1

    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, dict(OLD, test_steps="세 번째 내용"))
    assert _pick(_shown(s, p, run, u)) == _pick(NEW)


def test_고정_값은_TC_내용_칸을_전부_담는다(env):
    s, p, run, tc, u = env
    tc.custom_fields = {"환경": "iOS"}
    s.commit()
    complete_testrun(p.id, run.id, db=s, current_user=u)
    snap = s.query(TestResult).one().tc_snapshot

    columns = {c.name for c in TestCase.__table__.columns}
    meta = {"id", "project_id", "created_at", "updated_at", "created_by", "deleted_at", "no", "sheet_name"}
    assert set(snap) == columns - meta, "TC 에 새 칸이 생기면 고정 대상에도 넣어야 한다"
    assert snap["custom_fields"] == {"환경": "iOS"}


def test_고정된_보기는_값을_바꿀_수_없다(env):
    s, p, run, tc, u = env
    view = FrozenCase(tc, snapshot_of(tc))
    with pytest.raises(AttributeError):
        view.tc_id = "X"


def test_dict_로_만든_결과_응답도_test_case_를_받는다():
    body = TestResultResponse.model_validate({
        "id": 1, "test_run_id": 1, "test_case_id": 1, "result": "PASS", "executed_by": 1,
        "test_case": None,
    })
    assert body.test_case is None


# ── 내보내기 · 리포트 ────────────────────────────────────

def test_수행_엑셀은_종료_시점_내용이다(env):
    s, p, run, tc, u = env
    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, NEW)
    s.expire_all()

    resp = export_testrun_excel(p.id, run.id, db=s, current_user=u)
    async def collect():
        return b"".join([c async for c in resp.body_iterator])
    data = asyncio.run(collect())
    ws = load_workbook(io.BytesIO(data)).worksheets[0]
    row = [c.value for c in ws[2]]
    assert OLD["tc_id"] in row and OLD["test_steps"] in row
    assert NEW["tc_id"] not in row


def test_리포트_집계와_실패_목록은_종료_시점_분류와_우선순위로_센다(env):
    s, p, run, tc, u = env
    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, NEW)
    s.expire_all()

    assert [c["category"] for c in _category_summary_sql(run.id, s)] == [OLD["category"]]
    assert [r["priority"] for r in _priority_summary_sql(run.id, s)] == [OLD["priority"]]
    item = _issue_items(s.get(TestRun, run.id), s)[0]
    assert (item["tc_id"], item["test_steps"]) == (OLD["tc_id"], OLD["test_steps"])


def test_이전_수행_비교도_종료_시점_TC_ID_를_쓴다(env):
    s, p, run, tc, u = env
    complete_testrun(p.id, run.id, db=s, current_user=u)
    nxt = TestRun(project_id=p.id, name="R", round=2, created_by=u.id)
    s.add(nxt)
    s.flush()
    s.add(TestResult(test_run_id=nxt.id, test_case_id=tc.id, result=TestResultValue.PASS, executed_by=u.id))
    s.commit()
    complete_testrun(p.id, nxt.id, db=s, current_user=u)
    _edit(s, tc, NEW)
    s.expire_all()

    cmp = _comparison(s.get(TestRun, nxt.id), s)
    assert [f["tc_id"] for f in cmp["fixed"]] == [OLD["tc_id"]]


def test_수행_이슈도_종료_시점_TC_ID_로_보이고_그_ID_로_다시_연결된다(env):
    s, p, run, tc, u = env
    s.add(RunIssue(test_run_id=run.id, title="로그인 실패", url="https://x/ISS-1", issue_key="ISS-1", created_by=u.id,
                   test_cases=[tc]))
    s.commit()
    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, NEW)
    s.expire_all()

    issue = s.query(RunIssue).one()
    assert issue.tc_ids == [OLD["tc_id"]]
    assert issue.live_tc_ids == [NEW["tc_id"]]
    assert _run_issues(s.get(TestRun, run.id), s)[0]["tc_ids"] == [OLD["tc_id"]]
    # 화면은 받은 tc_ids 를 그대로 다시 보낸다. 지금 ID 로 찾으면 422 가 난다.
    assert [t.id for t in _resolve_test_cases(s, run.id, [OLD["tc_id"]])] == [tc.id]


# ── 이미 종료된 수행 채우기(마이그레이션) ───────────────────

def _migration_sql() -> str:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0009_result_tc_snapshot.py"
    spec = importlib.util.spec_from_file_location("m0009", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    executed = []

    class FakeOp:
        def add_column(self, *a, **k):
            pass

        def execute(self, sql):
            executed.append(sql)

    mod.op = FakeOp()
    mod.upgrade()
    assert len(executed) == 1
    return executed[0]


def test_마이그레이션은_이미_종료된_수행만_지금_TC_로_채운다(env):
    s, p, run, tc, u = env
    tc.custom_fields = {"k": "v"}
    run.status = TestRunStatus.completed
    other = TestRun(project_id=p.id, name="R2", round=1, created_by=u.id)
    s.add(other)
    s.flush()
    s.add(TestResult(test_run_id=other.id, test_case_id=tc.id, result=TestResultValue.NS, executed_by=u.id))
    s.commit()

    s.execute(text(_migration_sql()))
    s.commit()
    s.expire_all()

    done = s.query(TestResult).filter_by(test_run_id=run.id).one()
    live = s.query(TestResult).filter_by(test_run_id=other.id).one()
    assert done.tc_snapshot == snapshot_of(tc)
    assert live.tc_snapshot is None
    assert set(done.tc_snapshot) == set(SNAPSHOT_FIELDS)


def test_다음_회차로_이슈를_가져오면_지금_TC_로_잇는다(env):
    """종료된 원본 수행의 이슈는 종료 시점 ID 를 보인다. 새 회차는 진행 중이라 지금 ID 로 찾는다."""
    from routes.run_issues import carry_over_run_issues
    from schemas import RunIssueCarryOver

    s, p, run, tc, u = env
    s.add(RunIssue(test_run_id=run.id, title="로그인 실패", url="https://x/ISS-1", issue_key="ISS-1",
                   created_by=u.id, test_cases=[tc]))
    s.commit()
    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, NEW)
    nxt = TestRun(project_id=p.id, name="R", round=2, created_by=u.id)
    s.add(nxt)
    s.flush()
    s.add(TestResult(test_run_id=nxt.id, test_case_id=tc.id, result=TestResultValue.NS, executed_by=u.id))
    s.commit()

    carry_over_run_issues(p.id, nxt.id, RunIssueCarryOver(from_run_id=run.id), db=s, current_user=u)
    s.expire_all()

    carried = s.query(RunIssue).filter_by(test_run_id=nxt.id).one()
    assert carried.tc_ids == [NEW["tc_id"]], "가져온 이슈가 TC 연결을 잃었다"


def test_고정_값에_None_을_넣으면_SQL_NULL_이다(env):
    """기본 JSON 형은 None 을 JSON null 로 쓴다. 그러면 IS NULL 이 거짓이라 고정으로 읽힌다."""
    s, p, run, tc, u = env
    complete_testrun(p.id, run.id, db=s, current_user=u)
    r = s.query(TestResult).one()
    r.tc_snapshot = None
    s.commit()

    assert s.execute(text("SELECT count(*) FROM test_results WHERE tc_snapshot IS NULL")).scalar() == 1


def test_시트_이름을_바꾸면_완료된_수행도_새_시트에서_보인다(env):
    """QA 2인 지적. 시트 이름 변경은 완료된 수행의 범위(sheet_names)도 새 이름으로 바꾼다.
    결과가 옛 시트명을 들고 있으면 수행 화면의 새 이름 탭에서 그 결과가 걸러져 사라진다."""
    from routes.sheets import _SheetRename, rename_sheet

    s, p, run, tc, u = env
    run.sheet_names = ["S"]
    s.commit()
    complete_testrun(p.id, run.id, db=s, current_user=u)
    sheet = s.query(TestCaseSheet).filter_by(project_id=p.id, name="S").one()

    rename_sheet(p.id, sheet.id, _SheetRename(new_name="S3"), db=s, current_user=u)

    s.expire_all()
    assert s.get(TestRun, run.id).sheet_names == ["S3"]
    assert _shown(s, p, run, u)["sheet_name"] == "S3"


def test_이슈_TC_ID_는_이슈마다_쿼리하지_않는다(env, pg_engine):
    """QA1 지적. 예전 판은 tc_ids 를 읽을 때마다 SELECT 해 이슈 수 x 접근 횟수만큼 쿼리가 났다."""
    from sqlalchemy import event

    s, p, run, tc, u = env
    for i in range(5):
        s.add(RunIssue(test_run_id=run.id, title=f"이슈 {i}", url=f"https://x/ISS-{i}",
                       issue_key=f"ISS-{i}", created_by=u.id, test_cases=[tc]))
    s.commit()
    complete_testrun(p.id, run.id, db=s, current_user=u)
    _edit(s, tc, NEW)
    s.expire_all()
    loaded = s.get(TestRun, run.id)
    issues = list(loaded.issues)

    seen = []
    listener = lambda *a, **k: seen.append(1)  # noqa: E731
    event.listen(pg_engine, "before_cursor_execute", listener)
    try:
        ids = [i.tc_ids for i in issues] + [i.tc_ids for i in issues]
    finally:
        event.remove(pg_engine, "before_cursor_execute", listener)

    assert ids == [[OLD["tc_id"]]] * 10
    assert len(seen) <= 1, f"이슈 10번 읽는 데 쿼리 {len(seen)}번"
