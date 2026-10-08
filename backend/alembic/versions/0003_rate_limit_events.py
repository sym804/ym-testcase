"""횟수 제한 기록 테이블: rate_limit_events

로그인 실패 잠금과 계정 요청 접수 제한을 프로세스 메모리에서 DB 로 옮긴다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_rate_limit_events"
down_revision = "0002_unique_run_round"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bucket", sa.String(length=32), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rate_limit_events_bucket_key_created", "rate_limit_events",
                    ["bucket", "key", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rate_limit_events_bucket_key_created", table_name="rate_limit_events")
    op.drop_table("rate_limit_events")
