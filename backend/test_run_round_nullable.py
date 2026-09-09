"""라운드가 비어 있어도 수행 목록은 열려야 한다.

응답 스키마가 round 를 필수 정수로 두는데 컬럼은 NULL 을 받는다. 옛 데이터에
NULL 이 하나라도 있으면 그 프로젝트의 수행 목록 전체가 500 이 되고, 화면은
"등록된 테스트 수행이 없습니다" 로 그린다. 실 DB 에 2건 있었다.

이 파일이 보는 것은 셋이다: 모델 선언이 NOT NULL 인가(테이블은 create_all 로
만든다), 응답 스키마가 옛 NULL 을 견디는가, 수정 API 가 NULL 을 거절하는가.
마이그레이션이 batch 재생성에서 무엇을 잃는지는 test_migration_preserves_schema.py
가 본다. 여기서는 확인하지 않는다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dev_db_guard

# 이 파일도 HTTP 로 프로젝트를 만들고 지운다. 개발 서버가 떠 있으면 실 DB 를 친다.
if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def _models():
    """models 를 함수 안에서 들인다.

    ★모듈 최상단에서 import 하면 conftest 가 DATABASE_URL 을 임시 DB 로 바꾸기
      전에 엔진이 개발 DB 로 굳는다(test_result_uniqueness.py 와 같은 이유).
    """
    import models
    return models


@pytest.fixture
def session(tmp_path):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    m = _models()
    url = f"sqlite:///{(tmp_path / 'round.db').as_posix()}"
    engine = create_engine(url)
    m.Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s, engine
    s.close()
    engine.dispose()


def test_column_rejects_null_round(session):
    """모델이 선언한 테이블은 NULL 을 거부한다."""
    s, engine = session
    from sqlalchemy import inspect

    cols = {c["name"]: c for c in inspect(engine).get_columns("test_runs")}
    assert cols["round"]["nullable"] is False, "round 는 NULL 을 받으면 안 된다"


def test_column_rejects_null_round_at_write(session):
    """제약이 이름만 걸린 것이 아니라 실제로 막는지 본다."""
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    s, engine = session
    m = _models()
    user = m.User(username="u", password_hash="x", display_name="U")
    s.add(user)
    s.flush()
    project = m.Project(name="P", created_by=user.id)
    s.add(project)
    s.flush()

    with pytest.raises(IntegrityError):
        s.execute(text(
            "INSERT INTO test_runs (project_id, name, round, status, created_by, created_at) "
            "VALUES (:pid, 'legacy', NULL, 'in_progress', :uid, '2026-01-01 00:00:00')"
        ), {"pid": project.id, "uid": user.id})
        s.flush()
    s.rollback()


def test_update_rejects_null_round():
    """수행 수정에 round: null 을 보내면 400 으로 거절한다.

    NOT NULL 로 바꾼 뒤에는 이 값이 커밋에서 터져 500 이 된다. 읽기에서 나던 500 을
    쓰기로 옮기기만 하면 고친 것이 아니다.
    """
    import requests

    base = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
    pw = os.getenv("TEST_ADMIN_PASSWORD", "test1234")
    h = {"Authorization": "Bearer " + requests.post(
        f"{base}/api/auth/login", json={"username": "admin", "password": pw}
    ).json()["access_token"]}

    pid = requests.post(f"{base}/api/projects", headers=h, json={"name": "__round_null__"}).json()["id"]
    try:
        run_id = requests.post(f"{base}/api/projects/{pid}/testruns", headers=h,
                               json={"name": "r"}).json()["id"]

        r = requests.put(f"{base}/api/projects/{pid}/testruns/{run_id}", headers=h,
                         json={"round": None})

        assert r.status_code == 400, r.text
        got = requests.get(f"{base}/api/projects/{pid}/testruns", headers=h)
        assert got.status_code == 200, "목록이 여전히 열려야 한다"
    finally:
        requests.delete(f"{base}/api/projects/{pid}", headers=h)


def test_list_response_survives_null_round():
    """마이그레이션 전 DB 를 보는 서버가 있어도 목록 응답은 만들어져야 한다.

    컬럼 제약만 믿으면 그 서버에서 다시 500 이 난다. 읽는 쪽도 견디게 둔다.
    """
    from datetime import datetime

    from schemas import TestRunListResponse

    legacy = {
        "id": 1, "project_id": 1, "name": "legacy", "version": None,
        "environment": None, "round": None, "status": "in_progress",
        "sheet_names": None, "test_plan_id": None, "created_by": 1,
        "created_at": datetime(2026, 1, 1), "completed_at": None,
    }

    out = TestRunListResponse.model_validate(legacy)

    assert out.round == 1, "비어 있으면 1 라운드로 읽는다"
