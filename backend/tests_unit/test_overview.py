"""메인 화면 전체 현황 (SYM-225, 합격률 규칙은 SYM-133)

- 진행 중 수행과 최근 완료 수행을 따로 센다. 새 수행을 만들어도 최근 완료 수행 수치는 그대로다.
  예전에는 id 가 가장 큰 수행 하나로 세어 새 회차를 만들면 결과가 사라진 것처럼 보였다.
- 최근 완료는 completed_at 이 가장 늦은 수행이다(만든 순서가 아니다).
- 수치는 지금 남은 TC 기준이다(대시보드 수행 보기와 같다). 지운 TC 는 빠진다.
- 판정(PASS/FAIL/BLOCK)이 없으면 합격률은 0 이 아니라 None 이다.
- 비공개 프로젝트는 멤버가 아니면 안 보인다.

실행: cd backend && python -m pytest tests_unit/test_overview.py -q
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy.orm import sessionmaker

from models import (
    Project, ProjectMember, ProjectRole, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun,
    TestRunStatus, User, now_kst,
)
from routes.overview import global_overview

R = TestResultValue
BASE = datetime(2026, 9, 1, 10, 0)


@pytest.fixture
def env(pg_engine):
    db = sessionmaker(bind=pg_engine)()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.commit()
    yield db, user
    db.close()


def _project(env, name, n_tc=3, private=False, desc=None):
    db, user = env
    project = Project(name=name, description=desc, created_by=user.id, is_private=private)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in range(n_tc):
        tc = TestCase(project_id=project.id, no=n + 1, tc_id=f"{name}-{n + 1}", test_steps="1",
                      expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs.append(tc)
    db.commit()
    return project, tcs


def _run(env, project, tcs, results, hours, *, done_hours=None, name="R", rnd=1):
    """done_hours 를 주면 그 시각에 완료된 수행이다."""
    db, user = env
    run = TestRun(project_id=project.id, name=name, round=rnd, version="1.0", environment="stage",
                  status=TestRunStatus.completed if done_hours is not None else TestRunStatus.in_progress,
                  created_by=user.id, created_at=BASE + timedelta(hours=hours),
                  completed_at=BASE + timedelta(hours=done_hours) if done_hours is not None else None)
    db.add(run)
    db.flush()
    for tc, res in zip(tcs, results):
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=res, executed_by=user.id))
    db.commit()
    return run


def _overview(env, user=None):
    db, admin = env
    return global_overview(db=db, current_user=user or admin)


def _row(data, project):
    return next(p for p in data["projects"] if p["id"] == project.id)


# ── 진행 중 / 최근 완료 분리 ────────────────────────────────────────────────

def test_새_수행을_만들어도_최근_완료_수치는_그대로다(env):
    proj, tcs = _project(env, "A")
    done = _run(env, proj, tcs, (R.PASS, R.PASS, R.FAIL), 0, done_hours=1, rnd=1)
    new = _run(env, proj, tcs, (R.NS, R.NS, R.NS), 2, rnd=2)
    row = _row(_overview(env), proj)
    last = row["last_completed"]
    assert (last["run_id"], last["pass"], last["fail"], last["pass_rate"]) == (done.id, 2, 1, 66.7)
    assert [r["run_id"] for r in row["in_progress"]] == [new.id]
    assert row["in_progress"][0]["progress"] == 0.0 and row["in_progress"][0]["pass_rate"] is None


def test_진행_중_목록에는_진행_중_수행만_최신_시작_순으로(env):
    a, a_tcs = _project(env, "A")
    b, b_tcs = _project(env, "B")
    _run(env, a, a_tcs, (R.PASS,) * 3, 0, done_hours=1)
    ra = _run(env, a, a_tcs, (R.PASS, R.NS, R.NS), 2, name="A2")
    rb = _run(env, b, b_tcs, (R.FAIL, R.BLOCK, R.NS), 3, name="B1")
    data = _overview(env)
    assert [r["run_id"] for r in data["active_runs"]] == [rb.id, ra.id]
    first = data["active_runs"][0]
    assert (first["project_id"], first["project_name"], first["name"], first["round"]) == (b.id, "B", "B1", 1)
    assert (first["version"], first["environment"]) == ("1.0", "stage")
    assert (first["total"], first["executed"], first["fail"], first["block"]) == (3, 2, 1, 1)
    assert first["progress"] == 66.7 and first["pass_rate"] == 0.0


def test_최근_완료는_만든_순서가_아니라_완료_시각으로_고른다(env):
    proj, tcs = _project(env, "A")
    early_made = _run(env, proj, tcs, (R.PASS,) * 3, 0, done_hours=10, name="먼저 만들고 나중 완료")
    _run(env, proj, tcs, (R.FAIL,) * 3, 1, done_hours=5, name="나중 만들고 먼저 완료")
    assert _row(_overview(env), proj)["last_completed"]["run_id"] == early_made.id


def test_완료_시각이_빈_완료_수행보다_시각이_있는_수행이_먼저다(env):
    db, _ = env
    proj, tcs = _project(env, "A")
    dated = _run(env, proj, tcs, (R.PASS,) * 3, 0, done_hours=2, name="시각 있음")
    blank = _run(env, proj, tcs, (R.FAIL,) * 3, 1, done_hours=3, name="시각 없음")
    blank.completed_at = None  # 옛 데이터에 완료 시각 없이 완료된 수행이 있다
    db.commit()
    assert _row(_overview(env), proj)["last_completed"]["run_id"] == dated.id


def test_완료_시각이_모두_비면_나중에_만든_수행이다(env):
    db, _ = env
    proj, tcs = _project(env, "A")
    a = _run(env, proj, tcs, (R.PASS,) * 3, 0, done_hours=1)
    b = _run(env, proj, tcs, (R.FAIL,) * 3, 2, done_hours=3)
    a.completed_at = b.completed_at = None
    db.commit()
    assert _row(_overview(env), proj)["last_completed"]["run_id"] == b.id


def test_요약은_개수만_센다(env):
    a, a_tcs = _project(env, "A", n_tc=3)
    b, b_tcs = _project(env, "B", n_tc=2)
    _run(env, a, a_tcs, (R.FAIL, R.BLOCK, R.PASS), 0)
    _run(env, b, b_tcs, (R.FAIL, R.NS), 1)
    _run(env, b, b_tcs, (R.FAIL, R.FAIL), 2, done_hours=3)  # 완료 수행의 FAIL 은 세지 않는다
    s = _overview(env)["summary"]
    assert s == {"total_projects": 2, "active_tc": 5, "in_progress_runs": 2, "in_progress_fail_block": 3}


def test_프로젝트_행에_설명_생성일_활성_TC_를_싣는다(env):
    proj, _ = _project(env, "A", n_tc=4, desc="설명")
    row = _row(_overview(env), proj)
    assert (row["name"], row["description"], row["active_tc"], row["is_private"]) == ("A", "설명", 4, False)
    assert row["owner_name"] == "관리자", "소유자는 프로젝트를 만든 사람의 표시 이름"
    assert row["created_at"] is not None
    assert row["in_progress"] == [] and row["last_completed"] is None


# ── 지운 TC · 빈 수행 ────────────────────────────────────────────────────────

def test_지운_TC_는_집계와_활성_TC_에서_빠진다(env):
    db, _ = env
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.PASS, R.FAIL, R.NS), 0)
    tcs[1].deleted_at = now_kst()
    db.commit()
    data = _overview(env)
    row = _row(data, proj)
    run = row["in_progress"][0]
    assert (row["active_tc"], run["total"], run["fail"], run["pass_rate"]) == (2, 2, 0, 100.0)
    assert data["summary"]["active_tc"] == 2


def test_결과_행이_없는_진행_중_수행도_목록에_나온다(env):
    proj, _ = _project(env, "A")
    run = _run(env, proj, [], (), 0)
    r = _row(_overview(env), proj)["in_progress"][0]
    assert (r["run_id"], r["total"], r["progress"], r["pass_rate"]) == (run.id, 0, 0.0, None)


# ── 합격률 (SYM-133) ─────────────────────────────────────────────────────────

def test_판정_없는_수행의_합격률은_값이_없다(env):
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.NA, R.NA, R.NS), 0)
    r = _row(_overview(env), proj)["in_progress"][0]
    assert r["pass_rate"] is None and r["progress"] == 66.7


def test_FAIL_과_BLOCK_만_있으면_합격률은_0_이다(env):
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.FAIL, R.BLOCK, R.NS), 0)
    assert _row(_overview(env), proj)["in_progress"][0]["pass_rate"] == 0.0


# ── 권한 ─────────────────────────────────────────────────────────────────────

def test_비공개_프로젝트는_멤버가_아니면_안_보인다(env):
    db, _ = env
    pub, pub_tcs = _project(env, "공개")
    sec, sec_tcs = _project(env, "비공개", private=True)
    mine, mine_tcs = _project(env, "내 비공개", private=True)
    for p, t in ((pub, pub_tcs), (sec, sec_tcs), (mine, mine_tcs)):
        _run(env, p, t, (R.PASS,) * 3, 0)
    u = User(username="u", password_hash="x", display_name="U", role="user")
    db.add(u)
    db.flush()
    db.add(ProjectMember(project_id=mine.id, user_id=u.id, role=ProjectRole.tester))
    db.commit()
    data = _overview(env, user=u)
    assert {p["name"] for p in data["projects"]} == {"공개", "내 비공개"}
    assert {r["project_name"] for r in data["active_runs"]} == {"공개", "내 비공개"}
    assert data["summary"]["total_projects"] == 2


@pytest.mark.parametrize("role", ["admin", "qa_manager"])
def test_관리자와_QA_매니저는_비공개_프로젝트도_본다(env, role):
    db, _ = env
    sec, sec_tcs = _project(env, "비공개", private=True)
    _run(env, sec, sec_tcs, (R.PASS,) * 3, 0)
    u = User(username=f"m_{role}", password_hash="x", display_name="M", role=role)
    db.add(u)
    db.commit()
    data = _overview(env, user=u)
    assert [p["name"] for p in data["projects"]] == ["비공개"]
    assert [r["project_name"] for r in data["active_runs"]] == ["비공개"]


def test_완료_시각이_같으면_id_가_큰_수행이다(env):
    """만든 순서(created_at)를 id 와 반대로 두어 created_at 정렬로 바뀌면 걸리게 한다."""
    db, _ = env
    proj, tcs = _project(env, "A")
    later_made = _run(env, proj, tcs, (R.PASS,) * 3, 5, done_hours=10)
    early_made = _run(env, proj, tcs, (R.FAIL,) * 3, 1, done_hours=10)  # id 가 더 크다
    assert early_made.id > later_made.id
    assert _row(_overview(env), proj)["last_completed"]["run_id"] == early_made.id


def test_프로젝트는_최근_생성_순이다(env):
    """id 순서와 반대로 둔다. id 정렬로 바뀌면 걸린다."""
    db, _ = env
    first, _ = _project(env, "먼저 등록")
    second, _ = _project(env, "나중 등록")
    first.created_at = BASE + timedelta(days=1)
    second.created_at = BASE
    db.commit()
    assert second.id > first.id
    assert [p["name"] for p in _overview(env)["projects"]] == ["먼저 등록", "나중 등록"]


def test_소유자는_보는_사람이_아니라_만든_사람이다(env):
    db, admin = env
    other = User(username="maker", password_hash="x", display_name="홍길동", role="user")
    db.add(other)
    db.flush()
    p = Project(name="남이 만든", created_by=other.id)
    db.add(p)
    db.commit()
    data = _overview(env)  # 관리자가 본다
    assert _row(data, p)["owner_name"] == "홍길동"


def test_프로젝트가_없으면_빈_응답(env):
    data = _overview(env)
    assert data["projects"] == [] and data["active_runs"] == []
    assert data["summary"] == {"total_projects": 0, "active_tc": 0, "in_progress_runs": 0, "in_progress_fail_block": 0}
