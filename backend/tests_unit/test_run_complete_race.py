"""결과 저장과 수행 완료 · 재오픈의 경합

- 완료 · 재오픈도 결과 저장과 같은 수행 잠금(RUN_RESULTS)을 잡는다.
- 저장 · 가져오기는 잠금을 얻은 뒤 상태를 다시 읽어, 그 사이 완료됐으면 거절한다.
  예전에는 잠금 전에 읽은 "진행 중" 을 믿고 완료된 수행에 결과를 썼다.
- 이미 완료된 수행을 다시 완료해도 completed_at 은 그대로다.

실행: cd backend && python -m pytest tests_unit/test_run_complete_race.py -q
"""
import threading
import time
from datetime import datetime

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, TestRunStatus, User
from routes.testruns import _record_import, complete_testrun, reopen_testrun, submit_results
from schemas import TestResultCreate
from services.locks import LockNs
from services.result_import import parse_report


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
    s.add(TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False))
    tc = TestCase(project_id=p.id, no=1, tc_id="T-1", sheet_name="S", created_by=u.id)
    s.add(tc)
    run = TestRun(project_id=p.id, name="R", round=1, created_by=u.id)
    s.add(run)
    s.flush()
    s.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=TestResultValue.NS, executed_by=u.id))
    s.commit()
    yield Session, s, p, run, tc, u
    s.close()


def _hold(pg_engine, run_id):
    conn = pg_engine.connect()
    tx = conn.begin()
    conn.execute(text("SELECT pg_advisory_xact_lock(:ns, :k)"), {"ns": int(LockNs.RUN_RESULTS), "k": run_id})
    return conn, tx


@pytest.mark.parametrize("fn", [complete_testrun, reopen_testrun], ids=["complete", "reopen"])
def test_완료와_재오픈은_수행_잠금을_기다린다(env, pg_engine, monkeypatch, fn):
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "300")
    Session, s, p, run, tc, u = env
    conn, tx = _hold(pg_engine, run.id)
    try:
        with pytest.raises(HTTPException) as e:
            fn(p.id, run.id, db=s, current_user=u)
        assert e.value.status_code == 409
    finally:
        tx.rollback()
        conn.close()


def _wait_until_blocked(pg_engine, timeout=5.0):
    """다른 연결이 advisory 잠금을 기다리기 시작할 때까지 본다."""
    deadline = time.time() + timeout
    with pg_engine.connect() as c:
        while time.time() < deadline:
            n = c.execute(text(
                "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND NOT granted"
            )).scalar()
            if n:
                return
            time.sleep(0.05)
    raise AssertionError("저장 요청이 잠금을 기다리지 않았다")


def _race(env, pg_engine, monkeypatch, write):
    """write 가 잠금을 기다리는 사이 다른 연결이 수행을 완료로 바꾼다."""
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "10000")
    Session, s, p, run, tc, u = env
    conn, tx = _hold(pg_engine, run.id)
    out = {}

    def worker():
        ws = Session()
        try:
            wrun = ws.get(TestRun, run.id)
            wu = ws.get(User, u.id)
            write(ws, p, wrun, tc, wu)
            ws.commit()
            out["ok"] = True
        except HTTPException as e:
            ws.rollback()
            out["status"] = e.status_code
        finally:
            ws.close()

    th = threading.Thread(target=worker)
    th.start()
    try:
        _wait_until_blocked(pg_engine)
        with pg_engine.begin() as c:
            c.execute(text("UPDATE test_runs SET status = 'completed', completed_at = now() WHERE id = :i"),
                      {"i": run.id})
    finally:
        tx.rollback()
        conn.close()
    th.join(timeout=15)
    s.expire_all()
    row = s.query(TestResult).filter(TestResult.test_run_id == run.id).one()
    return out, row


def test_저장이_잠금을_기다리는_사이_완료되면_거절한다(env, pg_engine, monkeypatch):
    def write(ws, p, wrun, tc, wu):
        submit_results(p.id, wrun.id, [TestResultCreate(test_case_id=tc.id, result="PASS")], db=ws, current_user=wu)

    out, row = _race(env, pg_engine, monkeypatch, write)
    assert out.get("status") == 400, out
    assert row.result == TestResultValue.NS, "완료된 수행에 결과가 써졌다"


def test_가져오기가_잠금을_기다리는_사이_완료되면_거절한다(env, pg_engine, monkeypatch):
    fmt, entries = parse_report(b'<testsuite><testcase name="T-1 login" classname="x"/></testsuite>')

    def write(ws, p, wrun, tc, wu):
        _record_import(wrun, fmt, entries, ws, wu, dry_run=False, keep_executed=True, label=None)

    out, row = _race(env, pg_engine, monkeypatch, write)
    assert out.get("status") == 400, out
    assert row.result == TestResultValue.NS


def test_이미_완료된_수행을_다시_완료해도_완료_시각은_그대로다(env):
    Session, s, p, run, tc, u = env
    first = complete_testrun(p.id, run.id, db=s, current_user=u).completed_at
    time.sleep(0.01)
    again = complete_testrun(p.id, run.id, db=s, current_user=u)
    assert again.status == TestRunStatus.completed
    assert again.completed_at == first
