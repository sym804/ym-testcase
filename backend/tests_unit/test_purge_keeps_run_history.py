"""소프트 삭제 TC 의 7일 뒤 완전 삭제

리포트와 런 상세는 "그때의 수행 기록" 이라 런에 편입된 뒤 지워진 TC 의 결과도
그대로 센다. 그런데 완전 삭제가 그 TC 를 지우면 cascade 로 결과 행까지 사라져,
완료된 런의 총계가 8일째에 저절로 줄어든다. 보존하기로 한 기록이 시간이 지나면
없어지는 셈이다.

수행 기록에 한 번이라도 들어간 TC 는 완전 삭제 대상에서 뺀다. 화면에서는 이미
지워져 보이지 않고, 남는 것은 그 TC 를 참조하는 결과 행뿐이다.
"""
import os
import sys
from datetime import timedelta

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from models import (
    Base, Project, TestCase, TestResult, TestRun, TestResultValue, User, now_kst,
)
from services.purge_service import purge_deleted_testcases


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'purge.db'}".replace("\\", "/")
    engine = create_engine(url, connect_args={"check_same_thread": False})

    # 운영과 같게 외래키를 켠다. 꺼 두면 cascade 가 돌지 않아 이 테스트가
    # 통과해도 실제 동작을 보증하지 못한다.
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _seed(db, *, with_result: bool):
    user = User(username="u", password_hash="x", display_name="U", role="admin")
    db.add(user)
    db.flush()

    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()

    tc = TestCase(
        project_id=project.id, no=1, tc_id="TC-001", sheet_name="기본",
        test_steps="1. 실행", expected_result="성공", created_by=user.id,
        deleted_at=now_kst() - timedelta(days=8),
    )
    db.add(tc)
    db.flush()

    if with_result:
        run = TestRun(project_id=project.id, name="런", round=1, created_by=user.id)
        db.add(run)
        db.flush()
        db.add(TestResult(
            test_run_id=run.id, test_case_id=tc.id,
            result=TestResultValue.PASS, executed_by=user.id,
        ))
    db.commit()
    return tc.id


def test_수행에_들어간_TC는_8일이_지나도_지우지_않는다(db):
    tc_id = _seed(db, with_result=True)

    purge_deleted_testcases(db)

    assert db.query(TestCase).filter(TestCase.id == tc_id).first() is not None, (
        "수행 기록이 있는 TC 가 지워졌다. 리포트의 총계가 저절로 줄어든다"
    )
    assert db.query(TestResult).count() == 1, "결과 행이 cascade 로 사라졌다"


def test_수행에_안_들어간_TC는_8일이_지나면_지운다(db):
    tc_id = _seed(db, with_result=False)

    purge_deleted_testcases(db)

    assert db.query(TestCase).filter(TestCase.id == tc_id).first() is None, (
        "참조가 없는 TC 는 정리되어야 한다"
    )


def test_삭제한_지_얼마_안_된_TC는_건드리지_않는다(db):
    tc_id = _seed(db, with_result=False)
    tc = db.query(TestCase).filter(TestCase.id == tc_id).first()
    tc.deleted_at = now_kst() - timedelta(days=1)
    db.commit()

    purge_deleted_testcases(db)

    assert db.query(TestCase).filter(TestCase.id == tc_id).first() is not None


def test_살아_있는_TC는_건드리지_않는다(db):
    tc_id = _seed(db, with_result=False)
    tc = db.query(TestCase).filter(TestCase.id == tc_id).first()
    tc.deleted_at = None
    db.commit()

    purge_deleted_testcases(db)

    assert db.query(TestCase).filter(TestCase.id == tc_id).first() is not None
