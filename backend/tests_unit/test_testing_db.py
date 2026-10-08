"""테스트 DB 헬퍼

테스트가 원격 DB(특히 Supabase 운영)에 쓰는 일을 막는 것이 이 헬퍼의 첫째 일이다.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db
from sqlalchemy import create_engine, inspect, text


def test_원격_호스트는_거부한다(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+psycopg2://u:p@db.example.supabase.co:5432/postgres",
    )
    with pytest.raises(RuntimeError, match="로컬"):
        testing_db.admin_url()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_로컬_호스트는_허용한다(monkeypatch, host):
    monkeypatch.setenv("TEST_DATABASE_ADMIN_URL", f"postgresql+psycopg2://u:p@{host}:54329/postgres")
    assert host in testing_db.admin_url()


def test_임시_DB_를_만들고_지운다():
    url = testing_db.create_database(prefix="ymtc_selftest")
    try:
        eng = create_engine(url)
        with eng.connect() as c:
            assert c.execute(text("select 1")).scalar() == 1
        eng.dispose()
    finally:
        testing_db.drop_database(url)
    admin = create_engine(testing_db.admin_url(), isolation_level="AUTOCOMMIT")
    name = url.rsplit("/", 1)[1]
    with admin.connect() as c:
        left = c.execute(text("select 1 from pg_database where datname=:n"), {"n": name}).first()
    admin.dispose()
    assert left is None


def test_스키마_엔진은_서로_격리된다():
    base = testing_db.create_database(prefix="ymtc_selftest")
    try:
        a = testing_db.schema_engine(base)
        b = testing_db.schema_engine(base)
        try:
            with a.begin() as c:
                c.execute(text(
                    "insert into users (username, password_hash, display_name, role, "
                    "must_change_password, token_version) values ('x','h','x','user',false,0)"
                ))
            with b.connect() as c:
                assert c.execute(text("select count(*) from users")).scalar() == 0
            assert "users" in inspect(a).get_table_names()
        finally:
            testing_db.dispose_schema_engine(a)
            testing_db.dispose_schema_engine(b)
    finally:
        testing_db.drop_database(base)
