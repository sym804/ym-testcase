"""TC 수정(단건 · 일괄)의 시트 이동과 지운 TC

- 시트를 옮기면 진행 중 수행에 맞춘다. 그 시트를 범위로 둔 수행이 상세를 열기 전에도
  대시보드 · 리포트가 같은 숫자를 보게 한다(생성 · 복제 · 복원 · 가져오기와 같다).
- 일괄 수정은 지운 TC 를 고치지 않는다(단건 수정과 같다).
- 일괄 수정도 빈 TC ID 를 받지 않는다.

실행: cd backend && python -m pytest tests_unit/test_tc_update_sync.py -q
"""
import os
import sys

import pytest
from pydantic import ValidationError

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, TestResult, TestRun, TestRunStatus, User, now_kst
from routes.testcases import bulk_update_testcases, update_testcase
from schemas import TestCaseBulkItem, TestCaseBulkUpdate, TestCaseUpdate


@pytest.fixture
def env(pg_engine):
    db = sessionmaker(bind=pg_engine)()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    db.add(TestCaseSheet(project_id=project.id, name="T", sort_order=1, is_folder=False))
    tc = TestCase(project_id=project.id, no=1, tc_id="A-1", sheet_name="S", created_by=user.id)
    db.add(tc)
    db.flush()
    # T 시트만 범위로 둔 진행 중 수행. 지금은 A-1 이 범위 밖이라 행이 없다.
    run = TestRun(project_id=project.id, name="T 범위", round=1, created_by=user.id,
                  sheet_names=["T"], status=TestRunStatus.in_progress)
    db.add(run)
    db.commit()
    yield db, project, user, tc, run
    db.close()


def _in_run(db, run, tc):
    return db.query(TestResult).filter(TestResult.test_run_id == run.id,
                                       TestResult.test_case_id == tc.id).count()


def test_단건_수정으로_시트를_옮기면_진행_중_수행에_들어간다(env):
    db, project, user, tc, run = env
    update_testcase(project.id, tc.id, TestCaseUpdate(sheet_name="T"), db=db, current_user=user)
    assert _in_run(db, run, tc) == 1


def test_일괄_수정으로_시트를_옮기면_진행_중_수행에_들어간다(env):
    db, project, user, tc, run = env
    bulk_update_testcases(project.id, TestCaseBulkUpdate(items=[TestCaseBulkItem(id=tc.id, sheet_name="T")]),
                          db=db, current_user=user)
    assert _in_run(db, run, tc) == 1


def test_일괄_수정은_지운_TC를_고치지_않는다(env):
    db, project, user, tc, run = env
    tc.deleted_at = now_kst()
    db.commit()
    out = bulk_update_testcases(project.id, TestCaseBulkUpdate(items=[TestCaseBulkItem(id=tc.id, tc_id="B-1")]),
                                db=db, current_user=user)
    assert out == []
    db.expire_all()
    assert db.get(TestCase, tc.id).tc_id == "A-1"


def test_일괄_수정은_빈_TC_ID를_받지_않는다():
    with pytest.raises(ValidationError):
        TestCaseBulkItem(id=1, tc_id="")
