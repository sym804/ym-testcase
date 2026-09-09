"""test_runs.round 를 NOT NULL 로

Revision ID: e5a83f21c760
Revises: d41b6c8e5a27
Create Date: 2026-09-09 00:00:00.000000

응답 스키마는 round 를 필수 정수로 읽는데 컬럼은 NULL 을 받았다. 옛 데이터에
NULL 이 하나라도 있으면 그 프로젝트의 수행 목록 전체가 500 이 되고, 화면은
"등록된 테스트 수행이 없습니다" 로 그린다. 실 DB 에 2건 있었다.

비어 있던 것은 1 라운드로 채운다. 라운드는 1 부터 세므로 값을 지어내는 것이
아니라 기본값을 명시하는 것이다.

★SQLite 는 컬럼 제약을 바꾸려면 테이블을 다시 만들어야 한다. alembic 의 batch
  모드는 기존 스키마를 읽어 새 테이블을 만드는데, 읽어 낸 것만 남는다. 그래서
  만들어질 테이블을 `copy_from` 으로 직접 준다. 모델을 import 하지 않고 이 시점의
  정의를 여기에 적어 둔다. 나중에 모델이 바뀌어도 이 마이그레이션은 그대로여야
  한다.
  이 프로젝트의 개발 DB 는 pre-Alembic 시절에 만들어져 컬럼이 ALTER TABLE 로
  덧붙은 자리가 있다(test_plan_id 는 completed_at 뒤에 있다). 그런 테이블은
  reflect 결과가 모델 선언과 어긋날 수 있어서, 다시 만들 모양을 추측에 맡기지
  않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a83f21c760"
down_revision: Union[str, Sequence[str], None] = "d41b6c8e5a27"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _test_runs(round_nullable: bool) -> sa.Table:
    """이 마이그레이션이 다루는 시점의 test_runs 정의.

    인덱스도 함께 적는다. copy_from 을 주면 alembic 이 기존 스키마를 읽지 않으므로,
    여기 없는 것은 새 테이블에도 없다.
    """
    meta = sa.MetaData()
    table = sa.Table(
        "test_runs",
        meta,
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "project_id", sa.Integer(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.String(50), nullable=True),
        sa.Column("environment", sa.String(100), nullable=True),
        sa.Column("round", sa.Integer(), nullable=round_nullable),
        sa.Column("status", sa.String(11), nullable=True),
        sa.Column("sheet_names", sa.JSON(), nullable=True),
        sa.Column(
            "test_plan_id", sa.Integer(),
            sa.ForeignKey("test_plans.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    sa.Index("ix_test_runs_project_id", table.c.project_id)
    sa.Index("ix_test_runs_status", table.c.project_id, table.c.status)
    return table


def upgrade() -> None:
    op.execute("UPDATE test_runs SET round = 1 WHERE round IS NULL")
    with op.batch_alter_table("test_runs", copy_from=_test_runs(round_nullable=True)) as batch:
        batch.alter_column(
            "round",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="1",
        )


def downgrade() -> None:
    with op.batch_alter_table("test_runs", copy_from=_test_runs(round_nullable=False)) as batch:
        batch.alter_column(
            "round",
            existing_type=sa.Integer(),
            nullable=True,
            server_default=None,
        )
