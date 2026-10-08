"""한 런에서 한 TC 의 결과 행은 하나다 (SYM-5).

결과 행을 만드는 경로가 셋이다(런 생성 / 런 동기화 / 결과 제출). 셋 다 "없는 것을
조회한 뒤 넣는" 모양이라 동시 요청에서 같은 쌍이 두 번 들어갈 수 있었다.
실제로 운영 DB 에 하나 있었다(run=25, case=5345).

이 파일은 HTTP 를 타지 않는다. 제약과 삽입 헬퍼, 그리고 마이그레이션의 병합 규칙만 본다.
다만 conftest 의 세션 autouse 픽스처가 여전히 uvicorn 을 띄운다. 이 파일이 서버를
쓰지 않을 뿐이지, 이 파일만 돌려도 서버는 뜬다(QA 지적).
"""
import os
import sys

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _app_models():
    """models 를 **함수 안에서** 들인다.

    ★모듈 최상단에서 import 하면 안 된다. models -> database 인데 database 는
      import 시점에 DATABASE_URL 을 읽어 엔진을 만든다. pytest 는 수집 단계에서
      테스트 모듈을 import 하므로, 최상단 import 는 conftest 의 세션 픽스처가
      DATABASE_URL 을 임시 DB 로 변경하기 **전에** 엔진을 운영 DB 로 굳혀 버린다.
      그러면 다른 테스트 파일이 운영 admin 비밀번호로 로그인하려다 전부 죽는다
      (2026-09-05 실측: 이 파일을 추가하자 test_security.py 169건이 에러).
    """
    import models
    return models


def _sync_service():
    from services import run_sync_service
    return run_sync_service



@pytest.fixture
def db(pg_engine):
    m = _app_models()
    Base, User, Project = m.Base, m.User, m.Project
    TestRun, TestRunStatus, TestCase = m.TestRun, m.TestRunStatus, m.TestCase
    engine = pg_engine
    s = sessionmaker(bind=engine)()
    user = User(username="u", password_hash="x", display_name="U", role="admin")
    s.add(user)
    s.flush()
    proj = Project(name="P", created_by=user.id)
    s.add(proj)
    s.flush()
    run = TestRun(project_id=proj.id, name="R", status=TestRunStatus.in_progress,
                  created_by=user.id)
    s.add(run)
    s.flush()
    cases = [TestCase(project_id=proj.id, no=i, tc_id=f"TC-{i:03d}", created_by=user.id)
             for i in (1, 2, 3)]
    s.add_all(cases)
    s.commit()
    s.info["user"], s.info["project"], s.info["run"] = user, proj, run
    s.info["cases"] = cases
    yield s
    s.close()


def _row(run, case, user, result=None):
    if result is None:
        result = _app_models().TestResultValue.NS
    return {"test_run_id": run.id, "test_case_id": case.id,
            "result": result, "executed_by": user.id}


# ── 제약 자체 ─────────────────────────────────────────────────────────────────

def test_유니크_인덱스가_스키마에_있다(db):
    """★제약이 실제로 걸렸는지 먼저 단언한다. 안 걸렸으면 아래 테스트는 무의미하다."""
    names = {i["name"] for i in inspect(db.get_bind()).get_indexes("test_results")}
    assert "uq_test_results_run_case" in names


def test_같은_런과_TC_로_두_번_넣으면_거부된다(db):
    run, user, case = db.info["run"], db.info["user"], db.info["cases"][0]
    TestResult = _app_models().TestResult
    db.add(TestResult(**_row(run, case, user)))
    db.commit()
    db.add(TestResult(**_row(run, case, user, _app_models().TestResultValue.PASS)))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_다른_런이면_같은_TC_라도_들어간다(db):
    run, user, case = db.info["run"], db.info["user"], db.info["cases"][0]
    m = _app_models()
    TestRun, TestRunStatus, TestResult = m.TestRun, m.TestRunStatus, m.TestResult
    other = TestRun(project_id=db.info["project"].id, name="R2",
                    status=TestRunStatus.in_progress, created_by=user.id)
    db.add(other)
    db.flush()
    TestResult = _app_models().TestResult
    db.add(TestResult(**_row(run, case, user)))
    db.add(TestResult(**_row(other, case, user)))
    db.commit()
    assert db.query(_app_models().TestResult).count() == 2


# ── 삽입 헬퍼 ─────────────────────────────────────────────────────────────────

def test_충돌_행은_건너뛰고_나머지는_들어간다(db):
    """★예외로 처리하면 세션이 죽어 나머지 행까지 못 넣는다. 그것을 막는지 본다."""
    run, user, cases = db.info["run"], db.info["user"], db.info["cases"]
    TestResult = _app_models().TestResult
    db.add(TestResult(**_row(run, cases[0], user)))
    db.commit()

    inserted = _sync_service().insert_results_ignoring_duplicates(
        db, [_row(run, c, user) for c in cases]      # 3개 중 1개는 이미 있다
    )
    db.commit()
    assert inserted == 2, "이미 있는 하나만 빠지고 둘은 들어가야 한다"
    assert db.query(_app_models().TestResult).count() == 3


def test_빈_목록은_아무_일도_안_한다(db):
    assert _sync_service().insert_results_ignoring_duplicates(db, []) == 0


# ── 동기화 멱등성 ─────────────────────────────────────────────────────────────

def test_동기화를_두_번_돌려도_행이_안_늘어난다(db):
    run = db.info["run"]
    first = _sync_service().sync_run_results(run, db)
    assert first == 3
    second = _sync_service().sync_run_results(run, db)
    assert second == 0, "두 번째 호출은 새로 넣을 것이 없어야 한다"
    assert db.query(_app_models().TestResult).count() == 3


def test_완료된_런은_동기화하지_않는다(db):
    run = db.info["run"]
    run.status = _app_models().TestRunStatus.completed
    db.commit()
    assert _sync_service().sync_run_results(run, db) == 0
    assert db.query(_app_models().TestResult).count() == 0


# ── 마이그레이션의 병합 규칙 ──────────────────────────────────────────────────
