"""수행별 이슈 목록과 리포트 이슈 섹션

- 사람이나 MCP 가 제목과 주소를 넣는다. 키는 비우면 주소에서 뽑는다.
- 같은 주소는 한 수행에 한 번만 들어간다(409). 다시 채워도 중복이 쌓이지 않는다.
- 리포트 JSON, PDF, 엑셀 세 곳에 같은 목록이 실린다.
- 마이그레이션은 추가만 하고 기존 값을 건드리지 않는다.

실행: cd backend && python -m pytest tests_unit/test_run_issues.py -q
"""
import asyncio
import io
import os
import re
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from fastapi import HTTPException
from openpyxl import load_workbook
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker

from models import (
    Project, RunIssue, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, User,
)
from routes.reports import report_excel, report_json, report_pdf
from routes.run_issues import (
    carry_over_run_issues, create_run_issue, delete_run_issue, list_run_issues, update_run_issue,
)
from schemas import ProjectUpdate, RunIssueCarryOver, RunIssueCreate, RunIssueUpdate
from services.issue_key import extract_issue_key, find_issue_refs

LINEAR = "https://linear.app/sym/issue/SF-1081/세션-만료-후-재로그인"
JIRA = "https://acme.atlassian.net/browse/PROJ-12"


@pytest.fixture
def db(pg_engine, tmp_path):
    engine = pg_engine

    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def made(db):
    user = User(username="admin", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id, issue_tracker="linear")
    db.add(project)
    db.flush()
    run = TestRun(project_id=project.id, name="수행", round=1, created_by=user.id)
    db.add(run)
    db.commit()
    return project, run, user


def _add_tc(db, made, tc_id, no, *, link=None, result=TestResultValue.FAIL, in_run=True):
    """TC 하나를 만들고 in_run 이면 이 수행에 결과 행을 붙인다."""
    project, run, user = made
    if not db.query(TestCaseSheet).filter_by(project_id=project.id).first():
        db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tc = TestCase(project_id=project.id, no=no, tc_id=tc_id, priority="High", category="인증",
                  test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
    db.add(tc)
    db.flush()
    if in_run:
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=result,
                          issue_link=link, executed_by=user.id))
    db.commit()
    return tc


def _add(db, made, **kw):
    project, run, user = made
    return create_run_issue(project.id, run.id, RunIssueCreate(**kw), db=db, current_user=user)


def _update(db, made, issue_id, **kw):
    project, run, user = made
    return update_run_issue(project.id, run.id, issue_id, RunIssueUpdate(**kw), db=db, current_user=user)


def _body(resp):
    async def collect():
        chunks = []
        async for c in resp.body_iterator:
            chunks.append(c if isinstance(c, bytes) else str(c).encode())
        return b"".join(chunks)

    return asyncio.run(collect())


# ── 키 추출 ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url, key", [
    (LINEAR, "SF-1081"),
    ("https://linear.app/sym/issue/sf-7", "SF-7"),
    (JIRA, "PROJ-12"),
    ("https://acme.atlassian.net/jira/software/projects/PROJ/boards/1?selectedIssue=PROJ-3", "PROJ-3"),
    ("https://tracker.example.com/items/ABC-44/detail", "ABC-44"),
    ("https://linear.app/sym/project/fix-123-abc", None),
    ("https://example.com/", None),
    (None, None),
])
def test_주소에서_키를_뽑는다(url, key):
    assert extract_issue_key(url) == key


# ── 입력 검증 ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("url", ["javascript:alert(1)", "linear.app/sym/issue/SF-1", "", "   "])
def test_http_주소만_받는다(url):
    with pytest.raises(ValidationError):
        RunIssueCreate(title="t", url=url)


def test_제목은_비울_수_없다():
    with pytest.raises(ValidationError):
        RunIssueCreate(title="   ", url=JIRA)


def test_빈_키와_상태는_NULL_이다():
    p = RunIssueCreate(title=" 제목 ", url=f"  {JIRA}  ", issue_key=" ", status="")
    assert (p.title, p.url, p.issue_key, p.status) == ("제목", JIRA, None, None)


@pytest.mark.parametrize("raw, stored", [("Linear", "linear"), ("jira", "jira"), ("", None), (None, None)])
def test_이슈_관리_도구_값(raw, stored):
    assert ProjectUpdate(issue_tracker=raw).issue_tracker == stored


def test_모르는_이슈_관리_도구는_거절한다():
    with pytest.raises(ValidationError):
        ProjectUpdate(issue_tracker="github")


# ── 등록·수정·삭제 ───────────────────────────────────────────────────────────

def test_키를_비우면_주소에서_뽑는다(db, made):
    issue = _add(db, made, title="세션 만료 후 재로그인 실패", url=LINEAR)
    assert issue.issue_key == "SF-1081"


def test_손으로_적은_키는_그대로_둔다(db, made):
    issue = _add(db, made, title="t", url=LINEAR, issue_key="SYM-9")
    assert issue.issue_key == "SYM-9"


def test_같은_주소는_두_번_넣지_않는다(db, made):
    _add(db, made, title="첫 번째", url=LINEAR)
    with pytest.raises(HTTPException) as e:
        _add(db, made, title="두 번째", url=LINEAR)
    assert e.value.status_code == 409
    assert db.query(RunIssue).count() == 1


def test_다른_수행에는_같은_주소를_넣을_수_있다(db, made):
    project, run, user = made
    _add(db, made, title="t", url=LINEAR)
    other = TestRun(project_id=project.id, name="수행", round=2, created_by=user.id)
    db.add(other)
    db.commit()
    create_run_issue(project.id, other.id, RunIssueCreate(title="t", url=LINEAR), db=db, current_user=user)
    assert db.query(RunIssue).count() == 2


def test_주소를_변경하면_뽑은_키도_따라_변경된다(db, made):
    issue = _add(db, made, title="t", url=LINEAR)
    issue = _update(db, made, issue.id, url=JIRA)
    assert issue.issue_key == "PROJ-12"


def test_주소를_변경해도_손으로_적은_키는_남는다(db, made):
    issue = _add(db, made, title="t", url=LINEAR, issue_key="SYM-9")
    issue = _update(db, made, issue.id, url=JIRA)
    assert issue.issue_key == "SYM-9"


def test_수정으로_다른_이슈와_주소가_겹치면_409(db, made):
    _add(db, made, title="a", url=LINEAR)
    b = _add(db, made, title="b", url=JIRA)
    with pytest.raises(HTTPException) as e:
        _update(db, made, b.id, url=LINEAR)
    assert e.value.status_code == 409


def test_보내지_않은_칸은_건드리지_않는다(db, made):
    issue = _add(db, made, title="t", url=LINEAR, status="Todo", note="메모")
    issue = _update(db, made, issue.id, status="Done")
    assert (issue.title, issue.status, issue.note) == ("t", "Done", "메모")


def test_다른_수행의_이슈는_고칠_수_없다(db, made):
    project, run, user = made
    issue = _add(db, made, title="t", url=LINEAR)
    other = TestRun(project_id=project.id, name="다른", round=1, created_by=user.id)
    db.add(other)
    db.commit()
    with pytest.raises(HTTPException) as e:
        update_run_issue(project.id, other.id, issue.id, RunIssueUpdate(title="x"), db=db, current_user=user)
    assert e.value.status_code == 404


def test_삭제와_목록(db, made):
    project, run, user = made
    a = _add(db, made, title="a", url=LINEAR)
    _add(db, made, title="b", url=JIRA)
    delete_run_issue(project.id, run.id, a.id, db=db, current_user=user)
    assert [i.title for i in list_run_issues(project.id, run.id, db=db, current_user=user)] == ["b"]


def test_수행을_지우면_이슈도_지워진다(db, made):
    project, run, user = made
    _add(db, made, title="a", url=LINEAR)
    db.delete(run)
    db.commit()
    assert db.query(RunIssue).count() == 0


# ── 리포트 ───────────────────────────────────────────────────────────────────

def test_리포트_JSON_에_이슈와_도구가_실린다(db, made):
    project, run, user = made
    _add(db, made, title="세션 만료", url=LINEAR, status="In Progress")
    _add(db, made, title="필터 초기화", url=JIRA)
    data = report_json(project_id=project.id, run_id=run.id, db=db, current_user=user)
    assert data["project"]["issue_tracker"] == "linear"
    assert [(i["issue_key"], i["title"], i["status"]) for i in data["issues"]] == [
        ("SF-1081", "세션 만료", "In Progress"),
        ("PROJ-12", "필터 초기화", None),
    ]


GROUP_LABELS = ("미해결", "처리 완료")
GROUP_TITLE = re.compile(r"^(미해결|처리 완료) \(\d+\)$")


def _summary_issue_rows(ws):
    """요약 시트에서 "이슈 (n건)" 제목 아래 이슈 행을 (키, 제목, 심각도, 주소 셀, TC) 로 돌려준다.

    이슈는 묶음(미처리 · 신규 · 미확인 · 처리 완료)마다 소제목 + 머리행 + 행으로 실린다.
    """
    for row in ws.iter_rows(min_col=2, max_col=2):
        if str(row[0].value or "").startswith("이슈 ("):
            out, r = [], row[0].row + 2  # 제목 · 요약 줄 다음
            while True:
                label = str(ws.cell(r, 2).value or "")
                if not label.startswith(GROUP_LABELS):
                    break
                head = r + 1
                assert [ws.cell(head, c).value for c in (2, 3, 5, 6, 7, 8, 9)] == [
                    "키", "제목", "발견", "상태", "연관 TC", "심각도", "링크"]
                r = head + 1
                while ws.cell(r, 3).value is not None:
                    out.append((ws.cell(r, 2).value, ws.cell(r, 3).value, ws.cell(r, 8).value, ws.cell(r, 9),
                                ws.cell(r, 7).value))
                    r += 1
                r += 1  # 묶음 사이 빈 줄
            return row[0].value, out
    return None, []


def _summary_issue_groups(ws):
    """요약 시트 이슈 섹션의 묶음 소제목 차례. 예: ["미처리 (1)", "처리 완료 (2)"]"""
    titles = [c.value for (c,) in ws.iter_rows(min_col=2, max_col=2) if isinstance(c.value, str)]
    return [t for t in titles if GROUP_TITLE.match(t)]


def test_엑셀_요약_시트에_이슈가_실린다(db, made):
    """리포트는 한 장으로 이번 수행을 다 보여 주는 것이 목적이다. 따로 시트를 두지 않는다."""
    project, run, user = made
    _add(db, made, title="=HYPERLINK(\"x\")", url=LINEAR, status="Todo", note="메모")
    _add(db, made, title="필터 초기화", url=JIRA)
    resp = report_excel(project_id=project.id, run_id=run.id, db=db, current_user=user)
    wb = load_workbook(io.BytesIO(_body(resp)))
    assert wb.sheetnames == ["Summary", "Results"]
    ws = wb["Summary"]
    heading, rows = _summary_issue_rows(ws)
    assert heading == "이슈 (2건)"
    # 도구 상태(Todo)는 싣지 않고, note 는 심각도 열이다
    assert [(k, sev) for k, _, sev, _, _ in rows] == [("SF-1081", "메모"), ("PROJ-12", None)]
    assert not str(rows[0][1]).startswith("="), "제목이 수식으로 실행되면 안 된다(CWE-1236)"
    assert rows[0][3].value == LINEAR and rows[0][3].hyperlink.target == LINEAR
    assert "Todo" not in [c.value for row in ws.iter_rows() for c in row]
    # 요약 표 바로 다음에 온다(PDF 와 같은 차례). 이 픽스처에는 TC 가 없어 분류 표가 없다.
    titles = [c.value for (c,) in ws.iter_rows(min_col=2, max_col=2) if isinstance(c.value, str)]
    assert titles.index("전체 현황") < titles.index("이슈 (2건)")
    # 이번 수행에서 처음 넣은 이슈는 해결 전이므로 미해결이다
    assert _summary_issue_groups(ws) == ["미해결 (2)"]
    assert "미해결 2 · 처리 완료 0" in titles


def test_엑셀_이슈_표는_우선순위_분류_표보다_위다(db, made):
    project, run, user = made
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tc = TestCase(project_id=project.id, no=1, tc_id="A-1", priority="High", category="인증",
                  test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
    db.add(tc)
    db.flush()
    db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=TestResultValue.FAIL, executed_by=user.id))
    db.commit()
    _add(db, made, title="t", url=LINEAR)
    wb = load_workbook(io.BytesIO(_body(report_excel(project_id=project.id, run_id=run.id, db=db, current_user=user))))
    titles = [c.value for (c,) in wb["Summary"].iter_rows(min_col=2, max_col=2) if isinstance(c.value, str)]
    i = titles.index("이슈 (1건)")
    assert titles.index("전체 현황") < i < titles.index("우선순위별 요약") < titles.index("카테고리별 요약")


def test_이슈가_없으면_엑셀에_이슈_표가_없다(db, made):
    project, run, user = made
    resp = report_excel(project_id=project.id, run_id=run.id, db=db, current_user=user)
    wb = load_workbook(io.BytesIO(_body(resp)))
    assert _summary_issue_rows(wb["Summary"]) == (None, [])


def test_PDF_에_한글_이슈가_실린다(db, made):
    project, run, user = made
    _add(db, made, title="세션 만료 후 재로그인 실패", url=LINEAR, status="Todo", note="재현 3회")
    resp = report_pdf(project_id=project.id, run_id=run.id, db=db, current_user=user)
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(_body(resp)))
    text = "".join(pg.extract_text() for pg in reader.pages)
    assert "이슈 (Linear) 1" in text
    assert "SF-1081" in text and "세션 만료 후 재로그인 실패" in text
    assert "Todo" not in text, "도구 상태는 싣지 않는다"
    assert "재현 3회" in text and "심각도" in text
    uris = [
        a.get_object()["/A"]["/URI"]
        for pg in reader.pages for a in (pg.get("/Annots") or [])
        if "/A" in a.get_object()
    ]
    assert any("linear.app/sym/issue/SF-1081" in u for u in uris), f"주소가 링크로 걸려야 한다: {uris}"


# ── 마이그레이션 ─────────────────────────────────────────────────────────────

def test_연관_TC_는_없어도_되고_여럿이어도_된다(db, made):
    _add_tc(db, made, "ASP-02", 2)
    _add_tc(db, made, "ASP-01", 1)
    none = _add(db, made, title="TC 없음", url=JIRA)
    many = _add(db, made, title="둘", url=LINEAR, tc_ids=["ASP-02", "ASP-01", "ASP-02"])
    assert none.tc_ids == []
    assert many.tc_ids == ["ASP-01", "ASP-02"], "TC 번호 순, 중복 없이"


def test_쉼표로_이은_TC_도_받는다():
    assert RunIssueCreate(title="t", url=JIRA, tc_ids=" ASP-01, ,ASP-02 ").tc_ids == ["ASP-01", "ASP-02"]


def test_수행에_없는_TC_는_거절한다(db, made):
    _add_tc(db, made, "ASP-01", 1)
    _add_tc(db, made, "OUT-1", 2, in_run=False)
    with pytest.raises(HTTPException) as e:
        _add(db, made, title="t", url=JIRA, tc_ids=["ASP-01", "OUT-1", "NOPE-9"])
    assert e.value.status_code == 422
    assert "OUT-1" in e.value.detail and "NOPE-9" in e.value.detail
    assert db.query(RunIssue).count() == 0


def test_수정으로_TC_를_변경하고_빈_목록으로_푼다(db, made):
    _add_tc(db, made, "ASP-01", 1)
    _add_tc(db, made, "ASP-02", 2)
    issue = _add(db, made, title="t", url=JIRA, tc_ids=["ASP-01"])
    assert _update(db, made, issue.id, tc_ids=["ASP-02"]).tc_ids == ["ASP-02"]
    assert _update(db, made, issue.id, title="제목만").tc_ids == ["ASP-02"], "안 보낸 칸은 그대로"
    assert _update(db, made, issue.id, tc_ids=[]).tc_ids == []


def test_TC_를_지우면_연결만_풀린다(db, made):
    tc = _add_tc(db, made, "ASP-01", 1)
    issue = _add(db, made, title="t", url=JIRA, tc_ids=["ASP-01"])
    db.query(TestResult).filter_by(test_case_id=tc.id).delete()
    db.delete(tc)
    db.commit()
    db.expire_all()
    assert db.get(RunIssue, issue.id).tc_ids == []


def test_리포트에_연관_TC_가_실린다(db, made):
    project, run, user = made
    _add_tc(db, made, "ASP-01", 1)
    _add(db, made, title="t", url=LINEAR, tc_ids=["ASP-01"])
    data = report_json(project_id=project.id, run_id=run.id, db=db, current_user=user)
    assert data["issues"][0]["tc_ids"] == ["ASP-01"]
    wb = load_workbook(io.BytesIO(_body(report_excel(project_id=project.id, run_id=run.id, db=db, current_user=user))))
    _, rows = _summary_issue_rows(wb["Summary"])
    assert rows[0][4] == "ASP-01"
    from pypdf import PdfReader
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(_body(
        report_pdf(project_id=project.id, run_id=run.id, db=db, current_user=user)))).pages)
    assert "연관 TC" in text and "ASP-01" in text


# ── 결과 칸에서 찾은 추가 후보 ───────────────────────────────────────────────

@pytest.mark.parametrize("text, refs", [
    ("SF-1081 · sf1006-issues #1 (Major/미등록)", [("SF-1081", None)]),
    ("starfort-issues #13 (Minor/미등록) · starfort-issues #14", []),
    (f"재현됨 {LINEAR}, SF-1081 참고", [("SF-1081", LINEAR)]),
    ("SF-1 · SF-2 · SF-1", [("SF-1", None), ("SF-2", None)]),
    ("https://docs.example.com/page.", [(None, "https://docs.example.com/page")]),
    (None, []),
])
def test_자유_문구에서_이슈를_찾는다(text, refs):
    assert find_issue_refs(text) == refs


def test_추가_후보는_등록하지_않은_것만_TC_와_함께(db, made):
    project, run, user = made
    _add_tc(db, made, "ASP-01", 1, link="SF-1081 · sf1006-issues #1 (Major/미등록)")
    _add_tc(db, made, "ASP-02", 2, link="SF-1085 · sf1006-issues #5")
    _add_tc(db, made, "ASP-03", 3, link="SF-1085", result=TestResultValue.PASS)
    _add_tc(db, made, "ASP-04", 4, link="starfort-issues #13 (Minor/미등록)")
    _add(db, made, title="등록됨", url=LINEAR)  # SF-1081
    data = report_json(project_id=project.id, run_id=run.id, db=db, current_user=user)
    assert data["issue_candidates"] == [
        {"issue_key": "SF-1085", "url": None, "tc_ids": ["ASP-02", "ASP-03"]},
    ]


# ── 이전 회차 이슈 가져오기와 판정 ───────────────────────────────────────────

def _r2(db, made, **kw):
    """같은 이름의 다음 회차. compare 대상은 자동으로 R1 이다."""
    project, run, user = made
    r2 = TestRun(project_id=project.id, name=run.name, round=run.round + 1, created_by=user.id, **kw)
    db.add(r2)
    db.commit()
    return r2


def _carry(db, project, run, user, from_run_id=None):
    payload = RunIssueCarryOver(from_run_id=from_run_id) if from_run_id else None
    return carry_over_run_issues(project.id, run.id, payload, db=db, current_user=user)


def test_판정은_네_값만_받고_비우면_NULL(db, made):
    assert RunIssueCreate(title="t", url=LINEAR, verdict=" Resolved ").verdict == "resolved"
    assert RunIssueCreate(title="t", url=LINEAR, verdict="").verdict is None
    with pytest.raises(ValidationError):
        RunIssueCreate(title="t", url=LINEAR, verdict="fixed")
    with pytest.raises(ValidationError):
        RunIssueUpdate(verdict="done")


def test_이번_수행에서_넣은_이슈는_신규다(db, made):
    project, run, user = made
    i = _add(db, made, title="t", url=LINEAR)
    assert (i.origin_run_id, i.origin_round, i.verdict) == (None, None, None)
    data = report_json(project_id=project.id, run_id=run.id, db=db, current_user=user)
    assert data["issues"][0]["group"] == "open" and data["issues"][0]["origin_round"] is None
    # 신규 이슈는 확인 대상이 아니라 미확인 수에 들지 않는다
    assert data["issue_summary"] == {"open": 1, "resolved": 0, "unverified": 0}


def test_발견_수행은_같은_프로젝트의_다른_수행이어야_한다(db, made):
    project, run, user = made
    with pytest.raises(HTTPException) as e:
        _add(db, made, title="t", url=LINEAR, origin_run_id=run.id)
    assert e.value.status_code == 422
    with pytest.raises(HTTPException) as e:
        _add(db, made, title="t", url=LINEAR, origin_run_id=9999)
    assert e.value.status_code == 422


def test_발견_수행을_주면_그_회차를_적고_null_이면_신규로_돌린다(db, made):
    project, run, user = made
    r2 = _r2(db, made)
    i = create_run_issue(project.id, r2.id, RunIssueCreate(title="t", url=LINEAR, origin_run_id=run.id, verdict="open"),
                         db=db, current_user=user)
    assert (i.origin_run_id, i.origin_round, i.verdict) == (run.id, 1, "open")
    i = update_run_issue(project.id, r2.id, i.id, RunIssueUpdate(origin_run_id=None), db=db, current_user=user)
    assert (i.origin_run_id, i.origin_round) == (None, None)


def test_이전_회차_이슈를_가져오면_미확인으로_들어오고_출처를_가리킨다(db, made):
    project, run, user = made
    _add_tc(db, made, "ASP-01", 1)
    _add(db, made, title="세션 만료", url=LINEAR, status="Dev Deployed", note="메모", tc_ids=["ASP-01"])
    _add(db, made, title="필터", url=JIRA)
    r2 = _r2(db, made)
    # R2 에는 ASP-01 만 담는다(결과 행). 없는 TC 는 연결에서 빠진다.
    tc = db.query(TestCase).filter_by(tc_id="ASP-01").one()
    db.add(TestResult(test_run_id=r2.id, test_case_id=tc.id, result=TestResultValue.PASS, executed_by=user.id))
    db.commit()

    res = _carry(db, project, r2, user)
    assert (res.from_run_id, res.from_run_round, res.added, res.skipped) == (run.id, 1, 2, 0)
    got = {i.url: i for i in list_run_issues(project.id, r2.id, db=db, current_user=user)}
    assert got[LINEAR].origin_run_id == run.id and got[LINEAR].origin_round == 1
    assert got[LINEAR].verdict == "unverified" and got[LINEAR].status == "Dev Deployed"
    assert got[LINEAR].note == "메모" and got[LINEAR].tc_ids == ["ASP-01"]
    assert got[JIRA].issue_key == "PROJ-12"
    # 다시 가져오면 같은 주소는 건너뛴다
    res = _carry(db, project, r2, user)
    assert (res.added, res.skipped) == (0, 2)
    # R1 은 그대로다
    assert [i.verdict for i in run.issues] == [None, None]


def test_가져온_이슈를_또_가져오면_원래_발견_수행을_가리킨다(db, made):
    project, run, user = made
    _add(db, made, title="t", url=LINEAR)
    r2 = _r2(db, made)
    _carry(db, project, r2, user)
    r3 = _r2(db, (project, r2, user))
    _carry(db, project, r3, user)
    i = list_run_issues(project.id, r3.id, db=db, current_user=user)[0]
    assert (i.origin_run_id, i.origin_round) == (run.id, 1)


def test_가져올_이전_회차가_없으면_404(db, made):
    project, run, user = made
    with pytest.raises(HTTPException) as e:
        _carry(db, project, run, user)
    assert e.value.status_code == 404


def test_출처를_고르면_그_수행에서_가져온다(db, made):
    project, run, user = made
    other = TestRun(project_id=project.id, name="다른 수행", round=1, created_by=user.id)
    db.add(other)
    db.commit()
    create_run_issue(project.id, other.id, RunIssueCreate(title="x", url=JIRA), db=db, current_user=user)
    res = _carry(db, project, run, user, from_run_id=other.id)
    assert (res.from_run_name, res.added) == ("다른 수행", 1)
    with pytest.raises(HTTPException) as e:
        _carry(db, project, run, user, from_run_id=run.id)
    assert e.value.status_code == 422


def test_리포트는_이슈를_미해결_처리완료로_나눈다(db, made):
    """묶음은 둘. 유지·부분·미확인·판정 없음·신규는 모두 미해결, 해결만 처리 완료. 묶음 안은 넣은 차례."""
    project, run, user = made
    urls = [f"https://acme.atlassian.net/browse/PROJ-{n}" for n in range(1, 6)]
    for u in urls:
        _add(db, made, title=u[-6:], url=u)
    r2 = _r2(db, made)
    _carry(db, project, r2, user)
    got = {i.url: i for i in list_run_issues(project.id, r2.id, db=db, current_user=user)}
    for u, v in zip(urls, ("resolved", "open", "partial", "unverified", None)):
        update_run_issue(project.id, r2.id, got[u].id, RunIssueUpdate(verdict=v), db=db, current_user=user)
    create_run_issue(project.id, r2.id, RunIssueCreate(title="새 이슈", url=LINEAR), db=db, current_user=user)

    data = report_json(project_id=project.id, run_id=r2.id, db=db, current_user=user)
    assert [(i["issue_key"], i["group"]) for i in data["issues"]] == [
        ("PROJ-2", "open"), ("PROJ-3", "open"), ("PROJ-4", "open"), ("PROJ-5", "open"),
        ("SF-1081", "open"), ("PROJ-1", "resolved"),
    ]
    assert data["issue_summary"] == {"open": 5, "resolved": 1, "unverified": 2}
    assert data["issues"][0]["origin_round"] == 1 and data["issues"][4]["origin_round"] is None

    ws = load_workbook(io.BytesIO(_body(report_excel(project_id=project.id, run_id=r2.id, db=db, current_user=user))))["Summary"]
    assert _summary_issue_groups(ws) == ["미해결 (5)", "처리 완료 (1)"]
    _, rows = _summary_issue_rows(ws)
    assert [r[0] for r in rows] == ["PROJ-2", "PROJ-3", "PROJ-4", "PROJ-5", "SF-1081", "PROJ-1"]
    assert ws.cell(rows[0][3].row, 5).value == "R1" and ws.cell(rows[0][3].row, 6).value == "유지"
    # 새 이슈는 판정 칸에 "신규". 이전 회차 이슈인데 판정이 없으면 빈 칸(PROJ-5)
    assert ws.cell(rows[4][3].row, 5).value == "이번 수행" and ws.cell(rows[4][3].row, 6).value == "신규"
    assert ws.cell(rows[3][3].row, 6).value is None
    assert ws.cell(rows[4][3].row, 2).value == "SF-1081"
    # 소제목은 묶음 색이다(미해결 빨강)
    group_cell = next(c for (c,) in ws.iter_rows(min_col=2, max_col=2) if c.value == "미해결 (5)")
    assert group_cell.font.color.rgb.endswith("CF222E")

    from pypdf import PdfReader
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(_body(
        report_pdf(project_id=project.id, run_id=r2.id, db=db, current_user=user)))).pages)
    summary = "미해결 5 · 처리 완료 1 (미해결 중 미확인 2)"
    assert summary in text
    # 묶음 소제목 차례. 요약 줄 뒤부터 찾는다.
    start = text.index(summary) + len(summary)
    assert text.index("미해결 5\n", start) < text.index("처리 완료 1\n", start)
    assert "부분 해결" in text and "R1" in text and "이번 수행" in text


def test_미확인_이슈의_연관_TC_가_전부_PASS_면_해결_후보다(db, made):
    """힌트일 뿐이다. TC 통과가 곧 해결가 아니라 판정은 사람이 변경한다."""
    project, run, user = made
    _add_tc(db, made, "ASP-01", 1)
    _add_tc(db, made, "ASP-02", 2)
    _add(db, made, title="a", url=LINEAR, tc_ids=["ASP-01", "ASP-02"])
    _add(db, made, title="b", url=JIRA)
    r2 = _r2(db, made)
    for tc_id, result in (("ASP-01", TestResultValue.PASS), ("ASP-02", TestResultValue.PASS)):
        tc = db.query(TestCase).filter_by(tc_id=tc_id).one()
        db.add(TestResult(test_run_id=r2.id, test_case_id=tc.id, result=result, executed_by=user.id))
    db.commit()
    _carry(db, project, r2, user)
    data = report_json(project_id=project.id, run_id=r2.id, db=db, current_user=user)
    by = {i["issue_key"]: i for i in data["issues"]}
    assert by["SF-1081"]["tcs_all_pass"] is True and by["SF-1081"]["verdict"] == "unverified"
    assert by["PROJ-12"]["tcs_all_pass"] is None
    ws = load_workbook(io.BytesIO(_body(report_excel(project_id=project.id, run_id=r2.id, db=db, current_user=user))))["Summary"]
    _, rows = _summary_issue_rows(ws)
    assert ws.cell(rows[0][3].row, 6).value == "미확인 (해결 후보)"
    # 하나라도 PASS 가 아니면 후보가 아니다
    res = db.query(TestResult).join(TestCase).filter(TestResult.test_run_id == r2.id, TestCase.tc_id == "ASP-02").one()
    res.result = TestResultValue.FAIL
    db.commit()
    data = report_json(project_id=project.id, run_id=r2.id, db=db, current_user=user)
    assert {i["issue_key"]: i["tcs_all_pass"] for i in data["issues"]}["SF-1081"] is False


def test_이름이_다른_수행에서_가져온_이슈는_발견_열에_수행_이름이_붙는다(db, made):
    """같은 이름의 이전 회차면 R1 만으로 충분하지만, 다른 수행이면 어느 수행인지 밝혀야 한다."""
    project, run, user = made
    _add(db, made, title="같은 이름", url=LINEAR)
    other = TestRun(project_id=project.id, name="Full 테스트", round=1, created_by=user.id)
    db.add(other)
    db.commit()
    create_run_issue(project.id, other.id, RunIssueCreate(title="다른 이름", url=JIRA), db=db, current_user=user)
    r2 = _r2(db, made)
    _carry(db, project, r2, user)                      # 같은 이름 R1 에서
    _carry(db, project, r2, user, from_run_id=other.id)  # 다른 이름에서

    data = report_json(project_id=project.id, run_id=r2.id, db=db, current_user=user)
    by = {i["issue_key"]: i for i in data["issues"]}
    assert by["SF-1081"]["origin_run_name"] == run.name and by["PROJ-12"]["origin_run_name"] == "Full 테스트"

    ws = load_workbook(io.BytesIO(_body(report_excel(project_id=project.id, run_id=r2.id, db=db, current_user=user))))["Summary"]
    _, rows = _summary_issue_rows(ws)
    origin = {r[0]: ws.cell(r[3].row, 5).value for r in rows}
    assert origin == {"SF-1081": "R1", "PROJ-12": "Full 테스트 R1"}

    from pypdf import PdfReader
    text = "".join(pg.extract_text() for pg in PdfReader(io.BytesIO(_body(
        report_pdf(project_id=project.id, run_id=r2.id, db=db, current_user=user)))).pages)
    # 발견 칸이 좁아 이름과 회차 사이에서 줄이 바뀔 수 있다
    import re
    assert re.search(r"Full 테스트\s+R1", text)
