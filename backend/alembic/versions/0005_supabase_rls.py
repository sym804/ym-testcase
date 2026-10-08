"""Supabase REST 노출 차단: 모든 테이블 RLS, anon·authenticated 권한 회수

Supabase 는 public 스키마의 테이블을 anon 키로 REST 노출한다. 아무 조치를 안 하면 users
(비밀번호 해시 포함)를 밖에서 읽을 수 있다. 이 앱은 그 REST 를 쓰지 않고 테이블 소유자로
직접 접속하므로 RLS 의 영향을 받지 않는다.

★anon 역할이 있을 때만 한다. 로컬과 CI 의 순수 PostgreSQL 에는 이 역할이 없다.
★새 테이블은 자동으로 RLS 가 켜지지 않는다. 테이블을 추가하는 마이그레이션은 RLS 도 켠다.
  tests_unit/test_rls_migration.py 가 빠뜨린 테이블을 잡는다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0005_supabase_rls"
down_revision = "0004_staged_uploads"
branch_labels = None
depends_on = None

_ROLES = ("anon", "authenticated")


def _present_roles(bind) -> list[str]:
    rows = bind.execute(sa.text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"))
    return [r[0] for r in rows]


def _tables(bind) -> list[str]:
    rows = bind.execute(sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
    return [r[0] for r in rows]


def upgrade() -> None:
    bind = op.get_bind()
    roles = _present_roles(bind)
    if "anon" not in roles:
        return
    who = ", ".join(roles)
    # Supabase 가 REST 로 노출하는 스키마는 public 이다. search_path 와 무관하게 public 을 본다.
    schema = '"public"'
    for table in _tables(bind):
        op.execute(f'ALTER TABLE "public"."{table}" ENABLE ROW LEVEL SECURITY')
    op.execute(f"REVOKE ALL ON ALL TABLES IN SCHEMA {schema} FROM {who}")
    op.execute(f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA {schema} FROM {who}")
    # 이 역할(마이그레이션을 돌리는 소유자)이 앞으로 만드는 객체에도 기본 권한을 주지 않는다.
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON TABLES FROM {who}")
    op.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {schema} REVOKE ALL ON SEQUENCES FROM {who}")


def downgrade() -> None:
    bind = op.get_bind()
    if "anon" not in _present_roles(bind):
        return
    for table in _tables(bind):
        op.execute(f'ALTER TABLE "public"."{table}" DISABLE ROW LEVEL SECURITY')
