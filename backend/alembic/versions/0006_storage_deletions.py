"""지우지 못한 저장소 객체 재시도 기록: storage_deletions

새 테이블은 RLS 가 자동으로 켜지지 않는다. Supabase(anon 역할이 있는 DB)에서는 여기서 켠다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_storage_deletions"
down_revision = "0005_supabase_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "storage_deletions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    bind = op.get_bind()
    roles = [r[0] for r in bind.execute(sa.text(
        "SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"))]
    if "anon" in roles:
        op.execute('ALTER TABLE public.storage_deletions ENABLE ROW LEVEL SECURITY')
        op.execute(f"REVOKE ALL ON public.storage_deletions FROM {', '.join(roles)}")


def downgrade() -> None:
    op.drop_table("storage_deletions")
