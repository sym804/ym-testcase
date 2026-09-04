"""add account_requests

Revision ID: 05f8800a57f5
Revises: 06933fddb519
Create Date: 2026-09-04 14:07:20.244219

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '05f8800a57f5'
down_revision: Union[str, Sequence[str], None] = '06933fddb519'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """계정 복구 요청 테이블 추가"""
    op.create_table(
        'account_requests',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('request_type', sa.Enum('find_id', 'reset_password', name='accountrequesttype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', 'completed', name='accountrequeststatus'), nullable=False),
        sa.Column('claimed_username', sa.String(length=100), nullable=True),
        sa.Column('claimed_display_name', sa.String(length=100), nullable=True),
        sa.Column('contact', sa.String(length=200), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('code_hash', sa.String(length=255), nullable=True),
        sa.Column('code_expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_account_requests_id', 'account_requests', ['id'])
    op.create_index('ix_account_requests_status_created', 'account_requests', ['status', 'created_at'])


def downgrade() -> None:
    """계정 복구 요청 테이블 제거"""
    op.drop_index('ix_account_requests_status_created', table_name='account_requests')
    op.drop_index('ix_account_requests_id', table_name='account_requests')
    op.drop_table('account_requests')
