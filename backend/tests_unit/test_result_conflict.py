"""결과 저장의 낙관적 잠금

- 화면이 읽어 둔 executed_at(expected_executed_at)이 서버 값과 다르면 409, 배치 전체 거절.
- 토큰을 보내지 않으면 예전처럼 저장한다(스크립트 · MCP 호환).
- 저장 응답의 executed_at 을 다음 토큰으로 쓰면 이어서 저장된다.

실행: cd backend && python -m pytest tests_unit/test_result_conflict.py -q
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models import Base, Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, User
from routes.testruns import submit_results
from schemas import TestResultCreate

R = TestResultValue


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'lock.db').as_posix()}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    a = User(username="a", password_hash="x", display_name="A", role="admin")
    b = User(username="b", password_hash="x", display_name="B", role="admin")
    db.add_all([a, b])
    db.flush()
    project = Project(name="P", created_by=a.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in (1, 2):
        tc = TestCase(project_id=project.id, no=n, tc_id=f"T-{n}", test_steps="1", expected_result="2",
                      sheet_name="S", created_by=a.id)
        db.add(tc)
        tcs.append(tc)
    run = TestRun(project_id=project.id, name="수행", round=1, created_by=a.id)
    db.add(run)
    db.flush()
    for tc in tcs:
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=R.NS, executed_by=a.id))
    db.commit()
    yield db, project, run, tcs, a, b
    db.close()
    engine.dispose()


def _save(env, user, rows):
    db, project, run, _, _, _ = env
    return submit_results(project.id, run.id, [TestResultCreate(**r) for r in rows], db=db, current_user=user)


def test_토큰이_어긋나면_409_이고_아무것도_저장하지_않는다(env):
    db, project, run, tcs, a, b = env
    row = db.query(TestResult).filter_by(test_case_id=tcs[0].id).one()
    token = row.executed_at.isoformat()
    # B 가 먼저 저장한다
    _save(env, b, [{"test_case_id": tcs[0].id, "result": "FAIL"}])
    # A 는 옛 토큰으로 두 행을 한 배치에 보낸다
    with pytest.raises(HTTPException) as e:
        _save(env, a, [
            {"test_case_id": tcs[0].id, "result": "PASS", "expected_executed_at": token},
            {"test_case_id": tcs[1].id, "result": "PASS"},
        ])
    assert e.value.status_code == 409 and "T-1" in e.value.detail
    db.expire_all()
    assert db.query(TestResult).filter_by(test_case_id=tcs[0].id).one().result == R.FAIL, "B 의 값이 남는다"
    assert db.query(TestResult).filter_by(test_case_id=tcs[1].id).one().result == R.NS, "같은 배치의 다른 행도 저장하지 않는다"


def test_토큰이_맞으면_저장되고_응답의_executed_at_이_다음_토큰이다(env):
    db, project, run, tcs, a, b = env
    token = db.query(TestResult).filter_by(test_case_id=tcs[0].id).one().executed_at.isoformat()
    saved = _save(env, a, [{"test_case_id": tcs[0].id, "result": "PASS", "expected_executed_at": token}])
    assert saved[0].result == R.PASS
    new_token = saved[0].executed_at.isoformat()
    assert new_token != token
    saved = _save(env, a, [{"test_case_id": tcs[0].id, "result": "BLOCK", "expected_executed_at": new_token}])
    assert saved[0].result == R.BLOCK
    with pytest.raises(HTTPException):
        _save(env, a, [{"test_case_id": tcs[0].id, "result": "NA", "expected_executed_at": token}])


def test_토큰_없이_보내면_예전처럼_저장한다(env):
    db, project, run, tcs, a, b = env
    _save(env, b, [{"test_case_id": tcs[0].id, "result": "FAIL"}])
    saved = _save(env, a, [{"test_case_id": tcs[0].id, "result": "PASS"}])
    assert saved[0].result == R.PASS
