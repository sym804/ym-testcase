"""attachments.test_result_id 인덱스 추가

Revision ID: c9e2f4a17b03
Revises: b7d3c9a1e450
Create Date: 2026-09-08 00:00:00.000000

런 하나의 첨부를 한 번에 받는 조회(`GET /api/attachments/by-run/{run_id}`)는
attachments 를 test_results 와 조인한다. 이 컬럼에 인덱스가 없어 SQLite 가
attachments 를 통째로 훑는다(실측 query plan: `SCAN a`). 행 단위 조회
(`WHERE test_result_id = ?`)도 같은 스캔을 탄다.

첨부가 쌓일수록 런을 열 때마다 전체 스캔이 붙으므로 인덱스를 건다.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9e2f4a17b03"
down_revision: Union[str, Sequence[str], None] = "b7d3c9a1e450"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX_NAME = "ix_attachments_test_result_id"


def upgrade() -> None:
    op.create_index(INDEX_NAME, "attachments", ["test_result_id"], unique=False)


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="attachments")
