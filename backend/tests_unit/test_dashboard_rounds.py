"""대시보드 라운드별 비교와 Pass/Fail 추이

예전에는 모든 수행을 회차 번호로만 묶고 번호마다 가장 최근 것 하나를 골랐다.
계정·세션 정책 R1 과 R2 가 Full 테스트를 밀어내 추이가 서로 다른 테스트를 이었고,
진행 중인 R2 는 0% 로 찍혀 폭락처럼 보였다(2026-09-30 실측).

실행: cd backend && python -m pytest tests_unit/test_dashboard_rounds.py -q
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
    Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, TestRunStatus, User,
)
from routes.dashboard import round_comparison

R = TestResultValue
BASE = datetime(2026, 9, 1, 10, 0)


@pytest.fixture
def env(pg_engine, tmp_path):
    engine = pg_engine

    db = sessionmaker(bind=engine)()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in range(4):
        tc = TestCase(project_id=project.id, no=n + 1, tc_id=f"T-{n + 1}", test_steps="1",
                      expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs.append(tc)
    db.commit()
    yield db, project, user, tcs
    db.close()
    engine.dispose()


def _run(env, name, round_, hours, results, status=TestRunStatus.completed):
    db, project, user, tcs = env
    run = TestRun(project_id=project.id, name=name, round=round_, status=status,
                  created_by=user.id, created_at=BASE + timedelta(hours=hours))
    db.add(run)
    db.flush()
    for tc, res in zip(tcs, results):
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=res, executed_by=user.id))
    db.commit()
    return run


def _rounds(env, **kw):
    db, project, user, _ = env
    return round_comparison(project.id, date_from=None, date_to=None, db=db, current_user=user,
                            **{"run_name": None, "version": None, **kw})


def test_같은_이름끼리만_회차로_묶는다(env):
    full = _run(env, "Full", 1, 0, [R.PASS, R.PASS, R.FAIL, R.PASS])
    p1 = _run(env, "정책", 1, 1, [R.PASS, R.FAIL, R.FAIL, R.PASS])
    p2 = _run(env, "정책", 2, 2, [R.PASS, R.PASS, R.PASS, R.FAIL])

    rows = _rounds(env)  # 기본은 가장 최근 수행(정책 R2)의 이름
    assert [(r["name"], r["round"], r["run_id"]) for r in rows] == [("정책", 1, p1.id), ("정책", 2, p2.id)]

    rows = _rounds(env, run_name="Full")
    assert [(r["round"], r["run_id"]) for r in rows] == [(1, full.id)], "R1 끼리 밀려 사라지지 않는다"


def test_합격률은_수행분이_분모이고_리포트와_같다(env):
    _run(env, "정책", 1, 0, [R.PASS, R.PASS, R.FAIL, R.NA])
    row = _rounds(env)[0]
    assert row["executed"] == 3
    assert row["pass_rate"] == 66.7, "N/A 를 분모에 넣으면 50.0 이 된다"
    assert row["fail_rate"] == 33.3


def test_실행이_0건인_회차는_합격률이_null_이다(env):
    _run(env, "정책", 1, 0, [R.PASS, R.FAIL, R.PASS, R.PASS])
    _run(env, "정책", 2, 1, [R.NS, R.NS, R.NS, R.NS], status=TestRunStatus.in_progress)
    r2 = _rounds(env)[1]
    assert (r2["status"], r2["executed"], r2["not_started"]) == ("in_progress", 0, 4)
    assert r2["pass_rate"] is None and r2["fail_rate"] is None, "0% 로 찍히면 폭락처럼 보인다"


def test_같은_이름_같은_회차면_가장_최근_것(env):
    _run(env, "정책", 1, 0, [R.FAIL] * 4)
    later = _run(env, "정책", 1, 1, [R.PASS] * 4)
    rows = _rounds(env)
    assert [r["run_id"] for r in rows] == [later.id]


def test_수행이_없으면_빈_목록(env):
    assert _rounds(env) == []
    _run(env, "정책", 1, 0, [R.PASS] * 4)
    assert _rounds(env, run_name="없는 이름") == []
