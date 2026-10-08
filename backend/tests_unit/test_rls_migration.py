"""Supabase 는 public 스키마 테이블을 anon 키로 REST 노출한다. RLS 를 켜고 권한을 회수한다.

앱은 테이블 소유자로 접속하므로 RLS 의 영향을 받지 않는다. RLS 는 REST 노출 차단용이지
프로젝트 간 접근 격리 수단이 아니다(그 격리는 앱의 권한 검사가 맡는다).

로컬과 CI 의 순수 PostgreSQL 에는 anon 역할이 없다. 이 테스트는 역할을 만들어 Supabase 와
같은 조건을 흉내 낸다(역할은 클러스터 단위라 한 번 만들면 남는다. 앱 접속에는 영향 없음).
"""
import os
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, text

import testing_db

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_supabase_roles():
    eng = create_engine(testing_db.admin_url(), isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        for role in ("anon", "authenticated"):
            if not c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": role}).first():
                c.execute(text(f"CREATE ROLE {role} NOLOGIN"))
    eng.dispose()


@pytest.fixture(scope="module")
def migrated():
    _ensure_supabase_roles()
    url = testing_db.create_database(prefix="ymtc_rls")
    # Supabase 는 public 에 기본 권한을 준다. 회수가 실제로 일어나는지 보려고 먼저 준다.
    eng = create_engine(url, isolation_level="AUTOCOMMIT")
    with eng.connect() as c:
        c.execute(text("GRANT USAGE ON SCHEMA public TO anon, authenticated"))
        c.execute(text("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated"))
    eng.dispose()
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    eng = create_engine(url)
    yield eng
    eng.dispose()
    testing_db.drop_database(url)


def _tables(conn):
    return [r[0] for r in conn.execute(text(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))]


def test_모든_테이블에_RLS_가_켜져_있다(migrated):
    """모델의 모든 테이블과 alembic_version. 새 테이블을 추가하며 RLS 를 빠뜨리면 여기서 깨진다."""
    import models

    with migrated.connect() as c:
        off = [r[0] for r in c.execute(text(
            "SELECT relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'r' AND NOT c.relrowsecurity"))]
        names = set(_tables(c))
    assert off == []
    assert set(models.Base.metadata.tables) | {"alembic_version"} <= names


def test_anon_과_authenticated_는_어떤_테이블도_못_읽고_못_쓴다(migrated):
    with migrated.connect() as c:
        leaks = []
        for t in _tables(c):
            for role in ("anon", "authenticated"):
                for priv in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                    if c.execute(text("SELECT has_table_privilege(:r, :t, :p)"),
                                 {"r": role, "t": f"public.{t}", "p": priv}).scalar():
                        leaks.append((role, t, priv))
    assert leaks == []


def test_앱_소유자는_그대로_읽고_쓴다(migrated):
    with migrated.begin() as c:
        c.execute(text("INSERT INTO users (username, password_hash, display_name, role, "
                       "must_change_password, token_version) VALUES ('rls','x','r','user',false,0)"))
        assert c.execute(text("SELECT count(*) FROM users WHERE username = 'rls'")).scalar() == 1
