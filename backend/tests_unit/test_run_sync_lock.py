"""수행 동기화와 재오픈이 잠금을 얻은 뒤의 상태를 본다

- 동기화는 잠금 전에 '진행 중' 을 봤어도, 잠금을 기다리는 사이 완료됐으면 넣지 않는다.
- 재오픈은 잠금을 기다리는 사이 완료가 커밋됐어도 진행 중으로 되돌린다.
  잠금 전에 읽은 객체 값이 이미 진행 중이면 같은 값 대입이 변경으로 잡히지 않아 완료가 남았다.
- 다른 요청이 먼저 넣어 0건만 넣은 동기화도 잠금을 응답 전에 푼다.

실행: cd backend && python -m pytest tests_unit/test_run_sync_lock.py -q
"""
import pytest
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

import routes.testruns as testruns_route
import services.locks as locks
from models import Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, TestRunStatus, User
from services import run_sync_service
from services.locks import LockNs


@pytest.fixture
def env(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    with Session() as s:
        u = User(username="u", password_hash="x", display_name="U", role="admin")
        s.add(u)
        s.flush()
        p = Project(name="P", created_by=u.id)
        s.add(p)
        s.flush()
        s.add(TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False))
        tc1 = TestCase(project_id=p.id, no=1, tc_id="T-1", sheet_name="S", created_by=u.id)
        tc2 = TestCase(project_id=p.id, no=2, tc_id="T-2", sheet_name="S", created_by=u.id)
        s.add_all([tc1, tc2])
        run = TestRun(project_id=p.id, name="R", round=1, created_by=u.id)
        s.add(run)
        s.flush()
        # tc2 는 결과 행이 없다(동기화 대상)
        s.add(TestResult(test_run_id=run.id, test_case_id=tc1.id, result=TestResultValue.NS, executed_by=u.id))
        s.commit()
        ids = {"user": u.id, "project": p.id, "run": run.id, "tc2": tc2.id}
    return Session, ids


def _before_lock(monkeypatch, module, sql, params):
    """잠금을 잡기 직전에 다른 연결로 sql 을 커밋한다(잠금을 기다리는 사이 끼어든 요청)."""
    real = locks.advisory_xact_lock
    fired = []

    def wrapped(db, ns, key=0):
        if not fired and ns == LockNs.RUN_RESULTS:
            fired.append(True)
            with db.get_bind().engine.begin() as conn:
                conn.execute(text(sql), params)
        return real(db, ns, key)

    monkeypatch.setattr(module, "advisory_xact_lock", wrapped)
    return fired


def _lock_free(engine, run_id) -> bool:
    # 트랜잭션 잠금으로 확인한다. 세션 잠금을 잡으면 풀지 않은 채 연결이 풀로 돌아간다.
    with engine.begin() as conn:
        return conn.execute(text("SELECT pg_try_advisory_xact_lock(:ns, :k)"),
                            {"ns": int(LockNs.RUN_RESULTS), "k": run_id}).scalar()


def test_잠금을_기다리는_사이_완료된_수행에는_동기화가_넣지_않는다(env, pg_engine, monkeypatch):
    Session, ids = env
    fired = _before_lock(monkeypatch, locks, "UPDATE test_runs SET status = 'completed' WHERE id = :id",
                         {"id": ids["run"]})
    with Session() as db:
        run = db.get(TestRun, ids["run"])
        inserted = run_sync_service.sync_run_results(run, db)

    assert fired
    assert inserted == 0
    with Session() as db:
        assert db.query(TestResult).filter_by(test_run_id=ids["run"]).count() == 1
    assert _lock_free(pg_engine, ids["run"])


def test_재오픈은_잠금을_기다리는_사이_완료가_끼어들어도_진행_중으로_되돌린다(env, monkeypatch):
    Session, ids = env
    _before_lock(monkeypatch, testruns_route,
                 "UPDATE test_runs SET status = 'completed', completed_at = now() WHERE id = :id",
                 {"id": ids["run"]})
    with Session() as db:
        user = db.get(User, ids["user"])
        testruns_route.reopen_testrun(ids["project"], ids["run"], db=db, current_user=user)

    with Session() as db:
        run = db.get(TestRun, ids["run"])
        assert run.status == TestRunStatus.in_progress
        assert run.completed_at is None


def test_다른_요청이_먼저_넣어_0건이어도_프로젝트_동기화는_잠금을_푼다(env, pg_engine, monkeypatch):
    Session, ids = env
    _before_lock(monkeypatch, locks,
                 "INSERT INTO test_results (test_run_id, test_case_id, result, executed_by) "
                 "VALUES (:r, :t, 'NS', :u)",
                 {"r": ids["run"], "t": ids["tc2"], "u": ids["user"]})
    with Session() as db:
        total = run_sync_service.sync_project_in_progress_runs(ids["project"], db)
        assert total == 0
        # 세션을 아직 닫지 않은 지금(응답을 보내기 전) 잠금이 풀려 있어야 한다
        assert _lock_free(pg_engine, ids["run"])
