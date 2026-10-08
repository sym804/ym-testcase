"""기준점 마이그레이션으로 만든 스키마가 현재 모델과 같다.

옛 이력과 비교하지 않는다. 운영 SQLite 는 Alembic 이전에 만들어져 stamp 된 DB 라
옛 이력의 결과와도 다르다. 비교 대상은 모델(Base.metadata) 하나다.
"""
import os
import subprocess
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db


@pytest.fixture(scope="module")
def migrated_url():
    url = testing_db.create_database(prefix="ymtc_baseline")
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        testing_db.drop_database(url)
    assert r.returncode == 0, r.stderr
    yield url
    testing_db.drop_database(url)


def test_리비전은_하나다():
    versions = os.path.join(BACKEND, "alembic", "versions")
    files = sorted(f for f in os.listdir(versions) if f.endswith(".py"))
    assert files == ["0001_postgresql_baseline.py"]


def test_모델과_차이가_없다(migrated_url):
    import models  # noqa: F401
    from database import Base

    eng = create_engine(migrated_url)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    eng.dispose()
    assert diff == []


def test_부분_유니크_인덱스_조건이_살아_있다(migrated_url):
    eng = create_engine(migrated_url)
    with eng.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE indexname IN ('uq_test_cases_project_tc_id', 'uq_test_cases_sheet_no')"
        )).all())
    eng.dispose()
    assert set(rows) == {"uq_test_cases_project_tc_id", "uq_test_cases_sheet_no"}
    for name, ddl in rows.items():
        assert "UNIQUE" in ddl and "deleted_at IS NULL" in ddl, (name, ddl)


def test_FK_삭제_동작이_모델과_같다(migrated_url):
    import models

    eng = create_engine(migrated_url)
    insp = inspect(eng)
    for table in models.Base.metadata.sorted_tables:
        db_fks = {(tuple(fk["constrained_columns"]), fk["referred_table"]): (fk.get("options") or {}).get("ondelete")
                  for fk in insp.get_foreign_keys(table.name)}
        for fk in table.foreign_keys:
            key = ((fk.parent.name,), fk.column.table.name)
            want = fk.ondelete.upper() if fk.ondelete else None
            got = db_fks[key].upper() if db_fks.get(key) else None
            assert got == want, (table.name, key, got, want)
    eng.dispose()
