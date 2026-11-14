"""API 키 범위: api_keys.scope (SYM-217)

full 은 키 주인의 권한 그대로, results 는 결과 업로드 경로만 부른다. 이미 발급한 키는 full 로
둔다. TC·수행 API 를 폭넓게 쓰는 스크립트의 키가 있어서 범위를 좁히면 바로 깨진다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_api_key_scope"
down_revision = "0009_result_tc_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("scope", sa.String(16), nullable=False, server_default="full"))


def downgrade() -> None:
    op.drop_column("api_keys", "scope")
