"""사용자별 프로젝트 순서: project_orders (SYM-228)

새 테이블은 RLS 가 자동으로 켜지지 않는다. Supabase(anon 역할이 있는 DB)에서는 여기서 켠다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_project_orders"
down_revision = "0010_api_key_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_orders",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("user_id", "project_id"),
    )
    # 프로젝트를 지울 때 project_id 로 찾는다(PK 는 user_id 가 앞이라 못 쓴다).
    op.create_index("ix_project_orders_project_id", "project_orders", ["project_id"])
    bind = op.get_bind()
    roles = [r[0] for r in bind.execute(sa.text(
        "SELECT rolname FROM pg_roles WHERE rolname IN ('anon', 'authenticated')"))]
    if "anon" in roles:
        op.execute('ALTER TABLE public.project_orders ENABLE ROW LEVEL SECURITY')
        op.execute(f"REVOKE ALL ON public.project_orders FROM {', '.join(roles)}")


def downgrade() -> None:
    op.drop_index("ix_project_orders_project_id", table_name="project_orders")
    op.drop_table("project_orders")
