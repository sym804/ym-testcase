"""test_runs.sheet_names 추가

Revision ID: d41b6c8e5a27
Revises: c9e2f4a17b03
Create Date: 2026-09-08 00:00:00.000000

테스트 수행을 시트 단위로 만들 수 있게 한다. 어떤 시트를 담는 런인지 저장해
두어야, 진행 중 런이 새로 만들어진 TC 를 흡수할 때(`run_sync_service`)도 같은
범위를 지킨다. 저장하지 않으면 다음 동기화에서 제외한 시트가 다시 들어온다.

NULL 은 프로젝트 전체를 뜻한다. 이 컬럼이 생기기 전에 만들어진 런은 전부 NULL
이므로 동작이 달라지지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d41b6c8e5a27"
down_revision: Union[str, Sequence[str], None] = "c9e2f4a17b03"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("test_runs", sa.Column("sheet_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("test_runs", "sheet_names")
