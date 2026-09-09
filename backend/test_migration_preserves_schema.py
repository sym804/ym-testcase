"""마이그레이션이 테이블을 다시 만들 때 스키마를 잃지 않는다.

SQLite 는 컬럼 제약을 바꾸려면 테이블을 다시 만들어야 한다(batch 모드). 그 과정에서
외래키 동작이나 인덱스가 조용히 빠지면 아무도 모른 채 넘어간다. 이 DB 는
`PRAGMA foreign_keys=ON` 이라, `ON DELETE SET NULL` 을 잃으면 테스트 플랜 삭제가
FK 위반으로 막힌다.

지금 alembic 은 batch 로 재생성해도 이것들을 지켜 준다(copy_from 을 빼고 돌려도
통과한다). 그래서 이 파일은 결함을 재현해서 만든 것이 아니라, 앞으로 batch 를 쓰는
마이그레이션이 늘어날 때를 대비한 가드다. alembic 버전이 올라가거나 다른 테이블에
같은 수법을 쓸 때 여기서 걸린다.

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_migration_preserves_schema.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

#: (테이블, 컬럼) -> 있어야 하는 ON DELETE 동작
EXPECTED_ONDELETE = {
    ("test_runs", "project_id"): "CASCADE",
    ("test_runs", "test_plan_id"): "SET NULL",
    ("test_results", "test_run_id"): "CASCADE",
    ("test_results", "test_case_id"): "CASCADE",
    ("test_cases", "project_id"): "CASCADE",
    ("attachments", "test_result_id"): "CASCADE",
}

#: 있어야 하는 인덱스
EXPECTED_INDEXES = {
    "test_runs": {"ix_test_runs_project_id", "ix_test_runs_status"},
    "test_cases": {"ix_test_cases_project_id_deleted", "ix_test_cases_sheet_name"},
}


@pytest.fixture(scope="module")
def migrated(tmp_path_factory):
    """빈 DB 에 마이그레이션을 처음부터 끝까지 돌린 결과.

    ★별도 프로세스로 돌린다. alembic/env.py 는 DATABASE_URL 환경변수를 config
      보다 먼저 보므로, 같은 프로세스에서 부르면 conftest 가 잡아 둔 테스트 DB 로
      새어 나간다.
    """
    import subprocess

    here = os.path.dirname(os.path.abspath(__file__))
    db = (tmp_path_factory.mktemp("mig") / "m.db").as_posix()
    url = f"sqlite:///{db}"

    env = dict(os.environ, DATABASE_URL=url)
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=here, env=env, capture_output=True, text=True, timeout=180,
    )
    assert r.returncode == 0, "마이그레이션 실패:\n" + r.stdout + r.stderr

    from sqlalchemy import create_engine

    engine = create_engine(url)
    yield engine
    engine.dispose()


def test_foreign_key_actions_survive(migrated):
    """batch 로 테이블을 다시 만들어도 ON DELETE 가 남아야 한다."""
    from sqlalchemy import inspect

    insp = inspect(migrated)
    lost = []
    for (table, column), action in EXPECTED_ONDELETE.items():
        if table not in insp.get_table_names():
            continue
        for fk in insp.get_foreign_keys(table):
            if column in fk["constrained_columns"]:
                got = (fk.get("options") or {}).get("ondelete")
                if (got or "").upper() != action:
                    lost.append(f"{table}.{column}: {got!r} (기대 {action!r})")
                break
        else:
            lost.append(f"{table}.{column}: 외래키 자체가 없다")

    assert not lost, "외래키 동작이 사라졌다: " + "; ".join(lost)


def test_indexes_survive(migrated):
    """인덱스도 남아야 한다."""
    from sqlalchemy import inspect

    insp = inspect(migrated)
    missing = []
    for table, names in EXPECTED_INDEXES.items():
        if table not in insp.get_table_names():
            continue
        have = {ix["name"] for ix in insp.get_indexes(table)}
        missing += [f"{table}.{n}" for n in names - have]

    assert not missing, "인덱스가 사라졌다: " + ", ".join(missing)


def test_round_is_not_null(migrated):
    """이 마이그레이션이 하려던 것 자체도 확인한다."""
    from sqlalchemy import inspect

    cols = {c["name"]: c for c in inspect(migrated).get_columns("test_runs")}
    assert cols["round"]["nullable"] is False
