"""sync schema - drop notifications table

Revision ID: 06933fddb519
Revises: 8925bb1ad2db
Create Date: 2026-04-09 22:45:06.342706

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '06933fddb519'
down_revision: Union[str, Sequence[str], None] = '8925bb1ad2db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """notifications 테이블 제거 (v1.1.0에서 모델 삭제됨)"""
    # SQLite에서 인덱스가 없을 수 있으므로 직접 DROP
    op.execute("DROP TABLE IF EXISTS notifications")

    # NOTE: FK ondelete, column type (TEXT→JSON, VARCHAR→Enum) 차이는
    # SQLite에서 런타임 영향이 없으므로 별도 마이그레이션하지 않음.
    # 새 DB는 initial schema에서 올바르게 생성됨.


def downgrade() -> None:
    """notifications 테이블 복원"""
    op.create_table('notifications',
        sa.Column('id', sa.INTEGER(), nullable=False),
        sa.Column('user_id', sa.INTEGER(), nullable=False),
        sa.Column('message', sa.VARCHAR(length=500), nullable=False),
        sa.Column('link', sa.VARCHAR(length=500), nullable=True),
        sa.Column('is_read', sa.BOOLEAN(), nullable=False),
        sa.Column('created_at', sa.DATETIME(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
