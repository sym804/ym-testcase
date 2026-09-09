"""시트 안에서 no 를 유일하게

Revision ID: a3d61f0c8be2
Revises: f2b7c04e91a8
Create Date: 2026-09-09 00:00:00.000000

`no` 는 시트 안 순번이다. 앞 리비전이 한 번 정리했지만, 번호를 넣는 길이 넷이라
(신규 생성, 복제, 임포트, 드래그 정렬) 그중 하나만 새도 다시 어긋난다. 규칙을
코드 규율에 맡기지 않고 DB 가 지키게 한다.

지운 행은 뺀다. 지운 번호를 다음 TC 가 가져갈 수 있어야 시트 안 번호에 구멍이
남지 않는다. 되살릴 때 겹치면 restore_testcase 가 빈 번호를 준다.

이 인덱스를 걸 수 있으려면 그 전에 중복이 없어야 한다. f2b7c04e91a8 이 그것을
만든다. 그래도 옛 데이터가 어떤 모양일지 모르므로 걸기 전에 한 번 더 훑는다.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3d61f0c8be2"
down_revision: Union[str, Sequence[str], None] = "f2b7c04e91a8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 중복이 하나라도 남아 있으면 인덱스 생성이 실패한다. 앞 리비전과 같은 방식으로
    # 한 번 더 맞춘 뒤에 건다.
    dup = conn.execute(sa.text(
        "SELECT COUNT(*) FROM ("
        " SELECT project_id, sheet_name, no FROM test_cases"
        " WHERE deleted_at IS NULL"
        " GROUP BY project_id, sheet_name, no HAVING COUNT(*) > 1)"
    )).scalar()
    if dup:
        conn.execute(sa.text("""
            CREATE TEMP TABLE _tc_rank_uq AS
            SELECT id, ROW_NUMBER() OVER (
                PARTITION BY project_id, sheet_name
                ORDER BY CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END, no, id
            ) AS rn
            FROM test_cases
        """))
        conn.execute(sa.text("""
            UPDATE test_cases
            SET no = (SELECT rn FROM _tc_rank_uq WHERE _tc_rank_uq.id = test_cases.id)
            WHERE EXISTS (SELECT 1 FROM _tc_rank_uq WHERE _tc_rank_uq.id = test_cases.id)
        """))
        conn.execute(sa.text("DROP TABLE temp._tc_rank_uq"))

    op.create_index(
        "uq_test_cases_sheet_no",
        "test_cases",
        ["project_id", "sheet_name", "no"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_test_cases_sheet_no", table_name="test_cases")
