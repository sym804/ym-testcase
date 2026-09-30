"""run_issues 테이블과 projects.issue_tracker 추가 - 리포트 이슈 섹션

Revision ID: a7d3e5c19f42
Revises: c2f8a90b3d14
Create Date: 2026-09-30 00:00:00.000000

리포트의 연관 이슈는 결과 행 issue_link 칸을 모은 것이라, 칸에 설명이 붙은
자유 문구가 그대로 배지가 되고 TC 에 묶이지 않은 이슈는 실을 수 없었다.
수행마다 이슈 목록(제목과 주소)을 따로 둔다. 이슈마다 연관 TC 를 0개 이상
연결한다(run_issue_test_cases).

test_runs.compare_run_id 는 리포트의 비교 대상 수행이다. NULL 이면 같은 이름의
이전 회차를 자동으로 쓴다.

projects.issue_tracker 는 이슈 관리 도구 종류(jira / linear)다. 기존 행은 NULL 로
두어 지금처럼 주소 모양으로 짐작한다.

run_issues.origin_run_id · origin_round 는 이슈를 처음 발견한 수행이다. NULL 이면
이번 수행에서 처음 발견한 것(신규)이고, 이전 회차에서 가져온 이슈는 그 회차를
가리킨다. verdict 는 이번 수행에서 QA 가 확인한 결과(resolved / open / partial /
unverified)다. 이슈 관리 도구의 상태(status)와 따로 둔다. 개발이 배포했다고
처리된 것이 아니라 QA 가 재현해 봐야 처리 완료이기 때문이다. 리포트는 이 둘로
이슈를 미처리 · 신규 · 미확인 · 처리 완료로 나눈다.

추가만 하고 기존 테이블의 값은 건드리지 않는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7d3e5c19f42"
down_revision: Union[str, Sequence[str], None] = "c2f8a90b3d14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("issue_tracker", sa.String(length=20), nullable=True))
    # 리포트의 비교 대상. NULL 이면 같은 이름의 이전 회차를 자동으로 쓴다.
    # ★batch 로 test_runs 를 다시 만들지 않는다. 다른 표가 이 표를 CASCADE 로 물고 있어
    #   다시 만드는 동안 결과 행이 지워질 수 있다. SQLite 는 NULL 기본값 컬럼이면
    #   ADD COLUMN 에 REFERENCES 를 붙일 수 있다.
    if op.get_bind().dialect.name == "sqlite":
        # Alembic 의 add_column 은 SQLite 에서 외래키를 붙이지 못한다(제약 ALTER 미지원).
        op.execute(
            "ALTER TABLE test_runs ADD COLUMN compare_run_id INTEGER "
            "REFERENCES test_runs (id) ON DELETE SET NULL"
        )
    else:
        op.add_column("test_runs", sa.Column("compare_run_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_test_runs_compare_run_id", "test_runs", "test_runs",
            ["compare_run_id"], ["id"], ondelete="SET NULL",
        )
    op.create_table(
        "run_issues",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("test_run_id", sa.Integer(), nullable=False),
        sa.Column("issue_key", sa.String(length=50), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        # 처음 발견한 수행. 수행이 지워져도 origin_round 가 남아 "이전 회차 이슈" 임은 안다.
        sa.Column("origin_run_id", sa.Integer(), nullable=True),
        sa.Column("origin_round", sa.Integer(), nullable=True),
        # QA 확인 결과. resolved / open / partial / unverified. NULL 은 아직 판정하지 않은 것.
        sa.Column("verdict", sa.String(length=20), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["test_run_id"], ["test_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["origin_run_id"], ["test_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_run_issues_id", "run_issues", ["id"])
    op.create_index("uq_run_issues_run_url", "run_issues", ["test_run_id", "url"], unique=True)
    op.create_table(
        "run_issue_test_cases",
        sa.Column("run_issue_id", sa.Integer(), nullable=False),
        sa.Column("test_case_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["run_issue_id"], ["run_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["test_case_id"], ["test_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_issue_id", "test_case_id"),
    )
    op.create_index("ix_run_issue_test_cases_case_id", "run_issue_test_cases", ["test_case_id"])


def downgrade() -> None:
    op.drop_index("ix_run_issue_test_cases_case_id", table_name="run_issue_test_cases")
    op.drop_table("run_issue_test_cases")
    op.drop_index("uq_run_issues_run_url", table_name="run_issues")
    op.drop_index("ix_run_issues_id", table_name="run_issues")
    op.drop_table("run_issues")
    op.drop_column("projects", "issue_tracker")
    with op.batch_alter_table("test_runs") as batch:
        batch.drop_column("compare_run_id")
