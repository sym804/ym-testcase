"""프로젝트 목록 합격률은 판정이 없으면 값이 없다 (SYM-133)

- 진행률 · 합격률은 프로젝트의 가장 최근 수행 하나로 계산한다(현재 회차 지표).
- 그 수행에 PASS/FAIL/BLOCK 이 하나도 없으면 합격률은 0 이 아니라 None 이다.
  0% 로 내면 앞 회차가 전부 PASS 여도 새 회차를 만드는 순간 폭락처럼 보인다.
- 전체 요약 합격률도 같다. 판정이 하나라도 있으면 그 판정으로 센다.

실행: cd backend && python -m pytest tests_unit/test_overview_pass_rate.py -q
"""
import os
import sys
from datetime import datetime, timedelta

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models import (
    Base, Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, TestRunStatus, User,
)
from routes.overview import global_overview

R = TestResultValue
BASE = datetime(2026, 9, 1, 10, 0)


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'ov.db').as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.commit()
    yield db, user
    db.close()
    engine.dispose()


def _project(env, name, n_tc=3):
    db, user = env
    project = Project(name=name, created_by=user.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in range(n_tc):
        tc = TestCase(project_id=project.id, no=n + 1, tc_id=f"{name}-{n + 1}", priority="높음", category="기능",
                      test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs.append(tc)
    db.commit()
    return project, tcs


def _run(env, project, tcs, results, hours):
    db, user = env
    run = TestRun(project_id=project.id, name="R", round=1, status=TestRunStatus.in_progress,
                  created_by=user.id, created_at=BASE + timedelta(hours=hours))
    db.add(run)
    db.flush()
    for tc, res in zip(tcs, results):
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=res, executed_by=user.id))
    db.commit()


def _overview(env):
    db, user = env
    return global_overview(db=db, current_user=user)


def _row(data, project):
    return next(p for p in data["projects"] if p["id"] == project.id)


def test_판정_없는_새_수행이면_합격률은_값이_없다(env):
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.PASS, R.PASS, R.PASS), 0)
    _run(env, proj, tcs, (R.NS, R.NS, R.NS), 1)
    row = _row(_overview(env), proj)
    assert row["pass_rate"] is None
    # 진행률은 여전히 최근 수행 기준이다(현재 회차는 시작 전)
    assert (row["progress"], row["not_started"]) == (0.0, 3)


def test_NA_만_있어도_합격률은_값이_없다(env):
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.NA, R.NA, R.NS), 0)
    row = _row(_overview(env), proj)
    assert row["pass_rate"] is None
    assert row["progress"] == 66.7


def test_판정이_있으면_합격률은_그대로다(env):
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.PASS, R.FAIL, R.NS), 0)
    assert _row(_overview(env), proj)["pass_rate"] == 50.0


def test_수행이_없는_프로젝트도_합격률은_값이_없다(env):
    proj, _ = _project(env, "A")
    data = _overview(env)
    assert _row(data, proj)["pass_rate"] is None
    assert data["summary"]["pass_rate"] is None


def test_전체_요약은_판정이_있는_프로젝트로만_센다(env):
    a, a_tcs = _project(env, "A")
    b, b_tcs = _project(env, "B")
    _run(env, a, a_tcs, (R.PASS, R.PASS, R.FAIL), 0)
    _run(env, b, b_tcs, (R.NS, R.NS, R.NS), 1)
    s = _overview(env)["summary"]
    assert s["pass_rate"] == 66.7


def test_프로젝트가_없으면_합격률은_값이_없다(env):
    assert _overview(env)["summary"]["pass_rate"] is None


def test_전체_요약은_프로젝트_합격률의_평균이_아니라_판정_합계다(env):
    a, a_tcs = _project(env, "A", n_tc=1)
    b, b_tcs = _project(env, "B", n_tc=4)
    _run(env, a, a_tcs, (R.PASS,), 0)
    _run(env, b, b_tcs, (R.PASS, R.FAIL, R.FAIL, R.FAIL), 1)
    # 평균이면 (100 + 25) / 2 = 62.5, 합계면 2 / 5 = 40.0
    assert _overview(env)["summary"]["pass_rate"] == 40.0


def test_FAIL_과_BLOCK_만_있으면_합격률은_0_이다(env):
    proj, tcs = _project(env, "A")
    _run(env, proj, tcs, (R.FAIL, R.BLOCK, R.NS), 0)
    data = _overview(env)
    assert _row(data, proj)["pass_rate"] == 0.0
    assert data["summary"]["pass_rate"] == 0.0


def test_모든_프로젝트의_최근_수행에_판정이_없으면_전체_합격률도_값이_없다(env):
    a, a_tcs = _project(env, "A")
    b, b_tcs = _project(env, "B")
    _run(env, a, a_tcs, (R.PASS, R.PASS, R.PASS), 0)
    _run(env, a, a_tcs, (R.NS, R.NS, R.NS), 1)
    _run(env, b, b_tcs, (R.NA, R.NA, R.NA), 2)
    assert _overview(env)["summary"]["pass_rate"] is None
