"""대시보드 전체 집계는 TC 별 마지막 판정 결과를 센다 (SYM-131)

- 나중 수행에 NS(미수행)로 담겼다고 앞 수행의 PASS/FAIL 이 미수행으로 바뀌지 않는다.
- NA 는 판정이라 결과로 센다. 한 번도 판정되지 않은 TC 만 미수행이다.
- 버전 묶음을 주면 그 묶음 안에서 같은 규칙이다.
- 수행을 고른 보기(run_id)는 그 수행의 결과 그대로다. NS 는 미수행이다.

실행: cd backend && python -m pytest tests_unit/test_dashboard_latest_executed.py -q
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
from routes.dashboard import category_breakdown, dashboard_summary, get_heatmap, priority_distribution

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
        tc = TestCase(project_id=project.id, no=n + 1, tc_id=f"T-{n + 1}", priority="높음", category="기능",
                      test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs.append(tc)
    db.commit()
    yield db, project, user, tcs
    db.close()
    engine.dispose()


def _run(env, name, results, hours, version=None):
    """results 는 TC 순서대로. None 이면 그 TC 를 수행에 담지 않는다."""
    db, project, user, tcs = env
    run = TestRun(project_id=project.id, name=name, round=1, version=version, status=TestRunStatus.completed,
                  created_by=user.id, created_at=BASE + timedelta(hours=hours))
    db.add(run)
    db.flush()
    for tc, res in zip(tcs, results):
        if res is not None:
            db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=res, executed_by=user.id))
    db.commit()
    return run


def _kw(env, **over):
    db, project, user, _ = env
    # 직접 부르면 Query 기본값이 객체로 오므로 인자를 전부 명시한다
    kw = dict(run_id=None, date_from=None, date_to=None, version=None, db=db, current_user=user)
    kw.update(over)
    return project.id, kw


def _summary(env, **over):
    pid, kw = _kw(env, **over)
    s = dashboard_summary(pid, **kw)
    return s["pass"], s["fail"], s["block"], s["na"], s["not_started"]


def test_나중_수행의_미수행이_앞_수행의_결과를_덮지_않는다(env):
    _run(env, "7월 실측", (R.PASS, R.PASS, R.FAIL, R.NS), 0)
    _run(env, "9월 새 수행", (R.NS, R.NS, R.NS, R.NS), 1)
    # 앞 수행의 PASS 2 · FAIL 1 이 그대로다. T-4 는 어디서도 판정되지 않아 미수행
    assert _summary(env) == (2, 1, 0, 0, 1)


def test_판정이_여러_번이면_가장_나중_판정을_센다(env):
    _run(env, "R1", (R.FAIL, R.PASS, R.BLOCK, R.PASS), 0)
    _run(env, "R2", (R.PASS, R.NS, R.FAIL, R.NA), 1)
    _run(env, "R3", (R.NS, R.NS, R.NS, R.NS), 2)
    # T-1 PASS(R2) · T-2 PASS(R1) · T-3 FAIL(R2) · T-4 NA(R2)
    assert _summary(env) == (2, 1, 0, 1, 0)


def test_한_번도_판정되지_않은_TC_만_미수행이다(env):
    _run(env, "R1", (R.NS, R.NS, None, None), 0)
    assert _summary(env) == (0, 0, 0, 0, 4)


def test_우선순위와_카테고리와_히트맵도_같은_기준이다(env):
    _run(env, "R1", (R.PASS, R.FAIL, R.FAIL, R.NS), 0)
    _run(env, "R2", (R.NS, R.NS, R.PASS, R.NS), 1)
    pid, kw = _kw(env)
    pri = priority_distribution(pid, **kw)
    assert [(p["priority"], p["pass"], p["fail"], p["not_started"]) for p in pri] == [("높음", 2, 1, 1)]
    cat = category_breakdown(pid, **kw)
    assert [(c["category"], c["pass"], c["fail"], c["not_started"]) for c in cat] == [("기능", 2, 1, 1)]
    heat = get_heatmap(pid, **kw)
    assert sum(h["fail_count"] for h in heat) == 1  # T-2 의 R1 FAIL. T-3 은 R2 에서 PASS


def test_버전_묶음_안에서도_미수행은_건너뛴다(env):
    _run(env, "옛 버전", (R.PASS, R.PASS, R.PASS, R.PASS), 0, version="v1.4")
    _run(env, "새 버전 R1", (R.FAIL, R.PASS, R.NS, R.NS), 1, version="v1.5")
    _run(env, "새 버전 R2", (R.NS, R.NS, R.NS, R.NS), 2, version="v1.5")
    # v1.5 묶음: R1 의 판정만. v1.4 의 PASS 는 끼지 않는다
    assert _summary(env, version="1.5") == (1, 1, 0, 0, 2)
    # 전체: T-1 FAIL(v1.5) · T-2 PASS(v1.5) · T-3 · T-4 PASS(v1.4)
    assert _summary(env) == (3, 1, 0, 0, 0)


def test_수행을_고르면_그_수행의_결과_그대로다(env):
    _run(env, "R1", (R.PASS, R.PASS, R.PASS, R.PASS), 0)
    r2 = _run(env, "R2", (R.FAIL, R.NS, R.NS, R.NS), 1)
    assert _summary(env, run_id=r2.id) == (0, 1, 0, 0, 3)


def test_지운_TC_는_세지_않는다(env):
    db, _, _, tcs = env
    _run(env, "R1", (R.PASS, R.PASS, R.PASS, R.PASS), 0)
    _run(env, "R2", (R.NS, R.NS, R.NS, R.NS), 1)
    tcs[0].deleted_at = BASE
    db.commit()
    assert _summary(env) == (3, 0, 0, 0, 0)


def test_기간_밖의_판정은_세지_않는다(env):
    _run(env, "8월 실측", (R.PASS, R.PASS, R.FAIL, R.PASS), -24 * 10)
    _run(env, "9월 새 수행", (R.FAIL, R.NS, R.NS, R.NS), 0)
    # 기간이 9월 수행만 덮으면 8월 판정은 빠진다. T-2 ~ T-4 는 그 기간 안에서 판정이 없어 미수행
    assert _summary(env, date_from="2026-09-01") == (0, 1, 0, 0, 3)
    # 기간을 넓히면 8월 판정이 다시 남는다
    assert _summary(env, date_from="2026-08-01") == (2, 2, 0, 0, 0)


def test_나중은_결과를_입력한_시각이_아니라_수행을_만든_순서다(env):
    db, _, _, _ = env
    r1 = _run(env, "R1", (R.NS, R.NS, R.NS, R.NS), 0)
    _run(env, "R2", (R.PASS, R.PASS, R.NS, R.NS), 1)
    # R2 를 판정한 뒤 R1 을 다시 열어 FAIL 로 입력해도 T-1 · T-2 는 R2 의 PASS 다
    for res in db.query(TestResult).filter(TestResult.test_run_id == r1.id):
        res.result = R.FAIL
        res.executed_at = BASE + timedelta(hours=5)
    db.commit()
    assert _summary(env) == (2, 2, 0, 0, 0)
