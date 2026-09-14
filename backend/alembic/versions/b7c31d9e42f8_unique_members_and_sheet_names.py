"""멤버와 시트 이름에 유니크 제약

조회 후 삽입만으로는 동시 요청을 막지 못한다. 멤버가 둘이면 권한 조회의
`.first()` 가 아무 역할이나 돌려주어 판정이 비결정적이 되고, 같은 이름의 시트가
둘이면 rename/delete 가 한쪽만 건드려 TC 의 sheet_name 이 어느 쪽을 가리키는지
정해지지 않는다.

기존 인덱스 `ix_project_members_project_user` 는 유니크가 아니라 새로 만든다.
적용 전에 중복이 있으면 인덱스 생성이 실패하므로 먼저 정리한다. 남길 행은
멤버는 가장 먼저 만들어진 것, 시트는 일반 시트를 우선하고 그다음 오래된 것이다.

**정리는 되돌릴 수 없다.** downgrade 는 인덱스만 비유일하게 되돌리고 지워진 행은
복구하지 않는다. 중복이 있는 DB 에 적용하기 전에 백업해야 한다. 이 프로젝트의
실 DB 에는 중복이 없어(멤버 6행, 시트 26행 모두 유일) 지워지는 행이 없다.

Revision ID: b7c31d9e42f8
Revises: a3d61f0c8be2
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7c31d9e42f8"
down_revision: Union[str, Sequence[str], None] = "a3d61f0c8be2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 중복 멤버 정리: 같은 (project_id, user_id) 에서 가장 오래된 행만 남긴다.
    conn.execute(sa.text("""
        DELETE FROM project_members
        WHERE id NOT IN (
            SELECT MIN(id) FROM project_members GROUP BY project_id, user_id
        )
    """))

    # 중복 시트 정리: 같은 (project_id, name) 에서 가장 오래된 행만 남긴다.
    # TC 는 sheet_name(문자열)으로 이어져 있어 행을 지워도 TC 는 그대로다.
    #
    # ★지우기 전에 하위 시트를 남는 쪽으로 옮긴다. parent_id 가 ON DELETE CASCADE 라
    #   그냥 지우면 하위 트리가 통째로 연쇄 삭제된다. 중복을 정리하려다 멀쩡한
    #   시트를 잃는 셈이다. FK 가 꺼진 연결에서는 삭제 대신 고아 parent_id 가
    #   남아, 켜졌는지 여부에 따라 결과가 갈린다. 어느 쪽도 두면 안 된다.
    # ★남길 행은 "일반 시트 우선, 그다음 오래된 것" 이다. 단순히 MIN(id) 로 고르면
    #   같은 이름의 폴더와 일반 시트가 겹칠 때 폴더가 남을 수 있다. TC 는
    #   sheet_name 문자열로 이어지므로, 그 TC 가 폴더 소속이 되어 시트 순서에서
    #   빠지고 수행 범위로도 고를 수 없게 된다. 담을 방법이 없는 TC 가 생긴다.
    keeper_sql = """
        SELECT s.id FROM test_case_sheets s
        WHERE s.id = (
            SELECT k.id FROM test_case_sheets k
            WHERE k.project_id = s.project_id AND k.name = s.name
            ORDER BY k.is_folder ASC, k.id ASC
            LIMIT 1
        )
    """

    conn.execute(sa.text(f"""
        UPDATE test_case_sheets
        SET parent_id = (
            SELECT k.id FROM test_case_sheets k
            WHERE k.project_id = (
                    SELECT dup.project_id FROM test_case_sheets dup
                    WHERE dup.id = test_case_sheets.parent_id
                  )
              AND k.name = (
                    SELECT dup.name FROM test_case_sheets dup
                    WHERE dup.id = test_case_sheets.parent_id
                  )
            ORDER BY k.is_folder ASC, k.id ASC
            LIMIT 1
        )
        WHERE parent_id IN (
            SELECT id FROM test_case_sheets WHERE id NOT IN ({keeper_sql})
        )
    """))

    conn.execute(sa.text(f"""
        DELETE FROM test_case_sheets
        WHERE id NOT IN ({keeper_sql})
    """))

    op.drop_index("ix_project_members_project_user", table_name="project_members")
    op.create_index(
        "ix_project_members_project_user",
        "project_members",
        ["project_id", "user_id"],
        unique=True,
    )
    op.create_index(
        "uq_test_case_sheets_project_name",
        "test_case_sheets",
        ["project_id", "name"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_test_case_sheets_project_name", table_name="test_case_sheets")
    op.drop_index("ix_project_members_project_user", table_name="project_members")
    op.create_index(
        "ix_project_members_project_user",
        "project_members",
        ["project_id", "user_id"],
    )
