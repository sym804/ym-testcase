"""api_keys 추가 - 스크립트 · CI 용 API 키

Revision ID: 5e0b8c2d4f17
Revises: a7d3e5c19f42
Create Date: 2026-10-01 00:00:00.000000

자동화 스크립트가 비밀번호로 로그인해 JWT 를 받아 쓰고 있었다. 계정 파일을 읽어야 하고,
로그아웃 · 비밀번호 변경이 일어나면 스크립트도 같이 끊긴다. 사용자별로 이름 붙인 키를
발급하고 하나씩 폐기할 수 있게 한다. 원문은 저장하지 않고 SHA-256 해시만 둔다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5e0b8c2d4f17"
down_revision: Union[str, Sequence[str], None] = "a7d3e5c19f42"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_id", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_id"),
    )
    op.create_index("ix_api_keys_id", "api_keys", ["id"])
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_index("ix_api_keys_id", table_name="api_keys")
    op.drop_table("api_keys")
