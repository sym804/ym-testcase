"""대시보드 버전 묶음 필터

- version 을 주면 그 버전 묶음의 수행만 본다. "v1.5" 와 "1.5" 는 한 묶음이다.
- 전체 모드는 예전처럼 모든 수행의 TC 별 최신 결과다.

실행: cd backend && python -m pytest tests_unit/test_dashboard_version.py -q
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
from routes.dashboard import dashboard_summary, get_heatmap, round_comparison, version_key

R = TestResultValue
BASE = datetime(2026, 9, 1, 10, 0)


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'dv.db').as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in range(3):
        tc = TestCase(project_id=project.id, no=n + 1, tc_id=f"T-{n + 1}", priority="High", category="c",
                      test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs.append(tc)
    db.commit()
    yield db, project, user, tcs
    db.close()
    engine.dispose()


def _run(env, name, version, hours, results):
    db, project, user, tcs = env
    run = TestRun(project_id=project.id, name=name, round=1, version=version, status=TestRunStatus.completed,
                  created_by=user.id, created_at=BASE + timedelta(hours=hours))
    db.add(run)
    db.flush()
    for tc, res in zip(tcs, results):
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=res, executed_by=user.id))
    db.commit()
    return run


def _summary(env, version=None):
    db, project, user, _ = env
    # 직접 부르면 Query 기본값이 객체로 오므로 인자를 전부 명시한다
    return dashboard_summary(project.id, run_id=None, date_from=None, date_to=None, version=version,
                             db=db, current_user=user)


def test_버전_키는_앞의_v_와_대소문자를_무시한다():
    assert version_key("v1.5") == version_key("1.5") == version_key(" V1.5 ") == "1.5"
    assert version_key(None) == ""


def test_버전을_주면_그_묶음의_수행만_본다(env):
    _run(env, "옛 테스트", "v1.4", 0, (R.PASS, R.PASS, R.PASS))
    _run(env, "새 테스트", "1.5", 1, (R.FAIL, R.NS, R.NS))
    # 전체: TC 별 최신 수행이 v1.5 라 그 결과(FAIL 1 · NS 2)다. v1.4 의 PASS 는 묻힌다
    all_ = _summary(env)
    assert (all_["pass"], all_["fail"], all_["not_started"]) == (0, 1, 2)
    # v1.5 묶음("1.5" 표기): 그 수행만. 수행하지 않은 TC 는 미수행
    v15 = _summary(env, version="v1.5")
    assert (v15["pass"], v15["fail"], v15["not_started"]) == (0, 1, 2)
    v14 = _summary(env, version="V1.4")
    assert (v14["pass"], v14["fail"], v14["not_started"]) == (3, 0, 0)


def test_히트맵과_회차도_버전_묶음을_따른다(env):
    db, project, user, _ = env
    _run(env, "옛 테스트", "v1.4", 0, (R.FAIL, R.FAIL, R.PASS))
    _run(env, "새 테스트", "v1.5", 1, (R.PASS, R.NS, R.NS))
    heat = get_heatmap(project.id, run_id=None, date_from=None, date_to=None, version="1.5", db=db, current_user=user)
    assert heat == []  # v1.5 에는 FAIL 이 없다
    heat_14 = get_heatmap(project.id, run_id=None, date_from=None, date_to=None, version="v1.4", db=db, current_user=user)
    assert sum(h["fail_count"] for h in heat_14) == 2  # v1.4 묶음 안에서는 FAIL 둘
    rounds = round_comparison(project.id, date_from=None, date_to=None, run_name=None, version="v1.4", db=db, current_user=user)
    assert [r["name"] for r in rounds] == ["옛 테스트"]
