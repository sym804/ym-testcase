"""수행 목록의 진행률과 다음 회차 복제

- 목록 응답에 tc_total · tc_executed 가 실린다(NS 는 수행한 것으로 세지 않는다).
- clone?next_round=true 는 이름을 그대로 두고 회차를 +1 한다.

실행: cd backend && python -m pytest tests_unit/test_run_next_round.py -q
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models import Base, Project, TestCase, TestCaseSheet, TestPlan, TestResult, TestResultValue, TestRun, User
from routes.testruns import clone_testrun, list_testruns

R = TestResultValue


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'nr.db').as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()
    engine.dispose()


@pytest.fixture
def env(db):
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in (1, 2, 3):
        tc = TestCase(project_id=project.id, no=n, tc_id=f"A-{n}", priority="High", category="c",
                      test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs.append(tc)
    db.commit()
    return db, project, user, tcs


def _run(env, name, round_, results, version="v1.5", plan_id=None):
    db, project, user, tcs = env
    run = TestRun(project_id=project.id, name=name, round=round_, version=version, created_by=user.id,
                  test_plan_id=plan_id)
    db.add(run)
    db.flush()
    for tc, r in zip(tcs, results):
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=r, executed_by=user.id))
    db.commit()
    return run


def test_목록에_진행률이_실린다(env):
    db, project, user, _ = env
    a = _run(env, "정책", 1, (R.PASS, R.FAIL, R.NS))
    b = _run(env, "빈 수행", 1, ())
    # 직접 부르면 Query 기본값이 객체로 오므로 limit · offset 을 명시한다
    items = {i.id: i for i in list_testruns(project.id, limit=500, offset=0, db=db, current_user=user)}
    assert (items[a.id].tc_total, items[a.id].tc_executed) == (3, 2), "NS 는 수행한 것이 아니다"
    assert (items[b.id].tc_total, items[b.id].tc_executed) == (0, 0)


def test_다음_회차는_이름을_두고_회차를_올리며_결과는_NS_다(env):
    db, project, user, _ = env
    plan = TestPlan(project_id=project.id, name="v1.5", created_by=user.id)
    db.add(plan)
    db.flush()
    r1 = _run(env, "정책", 1, (R.PASS, R.FAIL, R.PASS), plan_id=plan.id)
    _run(env, "정책", 3, (R.PASS, R.PASS, R.PASS), plan_id=plan.id)  # 회차가 띄엄띄엄이어도 최댓값 + 1
    _run(env, "다른 이름", 9, (R.PASS,))

    new = clone_testrun(project.id, r1.id, next_round=True, db=db, current_user=user)
    assert (new.name, new.round, new.version, new.test_plan_id) == ("정책", 4, "v1.5", plan.id)
    rows = db.query(TestResult).filter(TestResult.test_run_id == new.id).all()
    assert len(rows) == 3 and all(r.result == R.NS for r in rows)

    # 예전 복제는 그대로다: "(복제)" 이름과 같은 회차, 플랜은 잇지 않는다
    dup = clone_testrun(project.id, r1.id, next_round=False, db=db, current_user=user)
    assert (dup.name, dup.round, dup.test_plan_id) == ("정책 (복제)", 1, None)
