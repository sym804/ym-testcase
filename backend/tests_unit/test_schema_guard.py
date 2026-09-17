"""pre-Alembic DB 를 검증 없이 head 로 표시하지 않는다

테이블은 있는데 `alembic_version` 이 없으면 기존 코드는 그대로 `stamp(head)` 했다.
구버전 DB 에 `sheet_names` 나 유니크 인덱스가 없어도 "최신" 으로 표시되고, 그
사이 마이그레이션이 전부 건너뛰어진다. 그 뒤 API 가 없는 컬럼을 찾다가 죽거나
중복을 그대로 받아들인다.

어느 시점의 스키마인지 알 수 없는 DB 를 자동으로 고치려 들면 더 망가진다.
표지를 검사해 최신이면 표시하고, 아니면 멈추고 사람에게 알린다.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine, inspect as sa_inspect

from models import Base
from services.schema_guard import SchemaMismatch, assert_schema_is_current


def _engine(tmp_path, name="guard.db"):
    url = f"sqlite:///{tmp_path / name}".replace("\\", "/")
    return create_engine(url, connect_args={"check_same_thread": False})


def test_최신_스키마는_통과한다(tmp_path):
    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)

    assert_schema_is_current(sa_inspect(engine))  # 예외가 없으면 통과


def test_컬럼이_빠진_구버전은_멈춘다(tmp_path):
    engine = _engine(tmp_path, "old.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE test_runs DROP COLUMN sheet_names")

    with pytest.raises(SchemaMismatch) as exc:
        assert_schema_is_current(sa_inspect(engine))
    assert "sheet_names" in str(exc.value)


def test_어떤_컬럼이_없는지_알려_준다(tmp_path):
    engine = _engine(tmp_path, "old2.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE test_cases DROP COLUMN custom_fields")

    with pytest.raises(SchemaMismatch) as exc:
        assert_schema_is_current(sa_inspect(engine))
    msg = str(exc.value)
    assert "test_cases" in msg and "custom_fields" in msg


def test_token_version_이_없으면_멈춘다(tmp_path):
    """폐기 수단이 없는 DB 를 head 로 표시하면 인증이 통째로 죽는다.

    `users.token_version` 은 요청마다 읽힌다. 마이그레이션을 건너뛴 채 stamp 되면
    그 컬럼이 없어 모든 인증 요청이 SQL 오류로 떨어진다.
    """
    engine = _engine(tmp_path, "no_token_version.db")
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE users DROP COLUMN token_version")

    with pytest.raises(SchemaMismatch) as exc:
        assert_schema_is_current(sa_inspect(engine))
    assert "token_version" in str(exc.value)
