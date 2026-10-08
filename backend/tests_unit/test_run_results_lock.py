"""결과를 쓰는 세 경로(저장, 파일 가져오기, 누락 행 동기화)는 같은 수행 잠금을 먼저 잡는다.

가져오기는 결과를 읽고 keep_executed 를 판단한 뒤 쓴다. 잠그지 않으면 그 사이 사람이 저장한
값을 가져오기가 덮는다. 저장과 동기화는 누락 행을 서로 다른 순서로 넣어 교착 고리를 만든다
(QA1 지적). 여기서는 다른 연결이 수행 잠금을 쥐고 있을 때 각 경로가 기다리다 409 로
물러나는지 본다. 누락 행이 없는 동기화(일반 조회)는 잠금을 잡지 않아야 한다.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, User
from routes.testruns import _record_import, submit_results
from schemas import TestResultCreate
from services.locks import LockNs
from services.result_import import parse_report
from services.run_sync_service import sync_run_results


@pytest.fixture
def env(pg_engine, monkeypatch):
    monkeypatch.setenv("LOCK_WAIT_TIMEOUT_MS", "300")
    s = sessionmaker(bind=pg_engine)()
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

    holder = pg_engine.connect()
    tx = holder.begin()
    holder.execute(text("SELECT pg_advisory_xact_lock(:ns, :k)"), {"ns": int(LockNs.RUN_RESULTS), "k": run.id})
    yield s, p, run, tc, u
    tx.rollback()
    holder.close()
    s.close()


def test_저장은_수행_잠금을_기다린다(env):
    s, p, run, tc, u = env
    with pytest.raises(HTTPException) as e:
        submit_results(p.id, run.id, [TestResultCreate(test_case_id=tc.id, result="PASS")], db=s, current_user=u)
    assert e.value.status_code == 409


def test_가져오기는_수행_잠금을_기다린다(env):
    s, p, run, tc, u = env
    report = b'<testsuite><testcase name="T-1 login" classname="x"/></testsuite>'
    fmt, entries = parse_report(report)
    with pytest.raises(HTTPException) as e:
        _record_import(run, fmt, entries, s, u, dry_run=False, keep_executed=True, label=None)
    assert e.value.status_code == 409


def test_누락_행이_있는_동기화는_수행_잠금을_기다린다(env):
    s, p, run, tc, u = env
    s.add(TestCase(project_id=p.id, no=2, tc_id="T-2", sheet_name="S", created_by=u.id))
    s.commit()
    with pytest.raises(HTTPException) as e:
        sync_run_results(run, s, commit=False)
    assert e.value.status_code == 409


def test_누락_행이_없으면_동기화는_잠금을_잡지_않는다(env):
    s, p, run, tc, u = env
    assert sync_run_results(run, s, commit=False) == 0
