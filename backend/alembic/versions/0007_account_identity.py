"""계정 신원 칸: email, email_verified, google_sub, status. password_hash 를 비어도 되게.

account_requests 의 사용자 외래키를 SET NULL 로 바꾼다. 승인 대기 계정을 거절(삭제)할 때
복구 이력 때문에 삭제가 막히지 않게 한다.
★status 와 email_verified 는 서버 기본값이 있어야 한다. SQLite 이관 스크립트가 원본에 없는
  칸을 빼고 INSERT 한다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_account_identity"
down_revision = "0006_storage_deletions"
branch_labels = None
depends_on = None

_STATUS = sa.Enum("active", "pending", "disabled", name="userstatus")


def upgrade() -> None:
    _STATUS.create(op.get_bind(), checkfirst=True)
    op.add_column("users", sa.Column("email", sa.String(length=100), nullable=True))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.add_column("users", sa.Column("status", _STATUS, nullable=False, server_default="active"))
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_google_sub"), "users", ["google_sub"], unique=True)
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=True)
    for col in ("user_id", "resolved_by_id"):
        name = f"account_requests_{col}_fkey"
        op.drop_constraint(name, "account_requests", type_="foreignkey")
        op.create_foreign_key(name, "account_requests", "users", [col], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    for col in ("user_id", "resolved_by_id"):
        name = f"account_requests_{col}_fkey"
        op.drop_constraint(name, "account_requests", type_="foreignkey")
        op.create_foreign_key(name, "account_requests", "users", [col], ["id"])
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_index(op.f("ix_users_google_sub"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_column("users", "status")
    op.drop_column("users", "google_sub")
    op.drop_column("users", "email_verified")
    op.drop_column("users", "email")
    _STATUS.drop(op.get_bind(), checkfirst=True)
