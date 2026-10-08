"""스테이징 업로드 발급 기록: staged_uploads"""
from alembic import op
import sqlalchemy as sa

revision = "0004_staged_uploads"
down_revision = "0003_rate_limit_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staged_uploads",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=True),
        sa.Column("declared_size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_staged_uploads_created", "staged_uploads", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_staged_uploads_created", table_name="staged_uploads")
    op.drop_table("staged_uploads")
