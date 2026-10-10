"""수행 복제(다음 회차 · 복제 · CI 이름 가져오기)가 지운 TC 와 범위 밖 TC 를 넘기지 않는다

원본 수행은 한 번 담은 행을 빼지 않는다. 그래서 그 뒤 TC 를 지우거나 시트를 옮겨도
원본에는 행이 남는다. 복제가 원본 행을 그대로 베끼면 그 TC 가 새 회차에 NS 로 다시
들어간다. 새 수행을 만들 때(_new_run)와 같은 조건으로 걸러야 한다.

실행: cd backend && python -m pytest tests_unit/test_run_clone_scope.py -q
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, TestResult, TestResultValue, TestRun, User, now_kst
from routes.testruns import _clone_run, clone_testrun

R = TestResultValue


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
    tcs = {}
    for n, key in enumerate(("keep", "deleted", "moved"), 1):
        tc = TestCase(project_id=project.id, no=n, tc_id=f"A-{n}", priority="High", category="c",
                      test_steps="1", expected_result="2", sheet_name="S", created_by=user.id)
        db.add(tc)
        tcs[key] = tc
    db.commit()
    yield db, project, user, tcs
    db.close()


def _source_run(db, project, user, tcs, *, sheet_names):
    """세 TC 를 모두 담은 수행을 만든 뒤, 하나는 지우고 하나는 범위 밖 시트로 옮긴다."""
    run = TestRun(project_id=project.id, name="정책", round=1, created_by=user.id, sheet_names=sheet_names)
    db.add(run)
    db.flush()
    for tc in tcs.values():
        db.add(TestResult(test_run_id=run.id, test_case_id=tc.id, result=R.PASS, executed_by=user.id))
    tcs["deleted"].deleted_at = now_kst()
    tcs["moved"].sheet_name = "T"
    db.commit()
    return run


def _case_ids(db, run_id):
    return {r[0] for r in db.query(TestResult.test_case_id).filter(TestResult.test_run_id == run_id).all()}


@pytest.mark.parametrize("next_round", [True, False])
def test_복제는_지운_TC와_범위_밖_TC를_넘기지_않는다(env, next_round):
    db, project, user, tcs = env
    src = _source_run(db, project, user, tcs, sheet_names=["S"])

    new = clone_testrun(project.id, src.id, next_round=next_round, db=db, current_user=user)

    assert _case_ids(db, new.id) == {tcs["keep"].id}
    # 원본은 그대로다. 한 번 담은 행은 빼지 않는다.
    assert _case_ids(db, src.id) == {t.id for t in tcs.values()}


def test_전체_범위_수행의_복제는_지운_TC만_거른다(env):
    db, project, user, tcs = env
    src = _source_run(db, project, user, tcs, sheet_names=None)

    new = clone_testrun(project.id, src.id, next_round=True, db=db, current_user=user)

    # 범위가 없으면 시트를 옮겨도 대상이다. 지운 TC 만 빠진다.
    assert _case_ids(db, new.id) == {tcs["keep"].id, tcs["moved"].id}


def test_CI_이름_가져오기가_쓰는_복제도_같이_거른다(env):
    """import_results_by_name 은 같은 이름의 최신 회차를 _clone_run 으로 잇는다."""
    db, project, user, tcs = env
    src = _source_run(db, project, user, tcs, sheet_names=["S"])

    new = _clone_run(src, user, db, next_round=True)
    db.commit()

    assert _case_ids(db, new.id) == {tcs["keep"].id}
