"""TC ID 를 프로젝트 안에서 유일하게

Revision ID: b7d3c9a1e450
Revises: 06933fddb519
Create Date: 2026-09-07 16:05:00.000000

사전조건 참조("<TC-ID> 의 사전조건 참조")를 푸는 색인이 프로젝트 전체 TC 로
만들어지므로(`precondition_service.build_index`), 같은 TC ID 가 둘 있으면 참조가
어느 쪽을 가리키는지 정해지지 않는다. 내보내기의 펼친 사전조건이 엉뚱한 TC 내용을
담는 데이터 손상으로 이어진다.

소프트 삭제된 행은 제외한다(`deleted_at IS NULL` 부분 인덱스). 지운 TC 가 ID 를
계속 물고 있으면 같은 번호를 다시 쓸 수 없다.

이 마이그레이션은 앱 기동 시 자동 실행된다(`main.py` lifespan). 중복이 있는 DB 에서
실패해 앱이 안 뜨는 일을 막으려고, 인덱스를 걸기 전에 중복을 스스로 정리한다.
정리 내역은 WARNING 으로 남기니 나중에 사람이 확인해 고칠 수 있다.
"""
import logging
from typing import Sequence, Set, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7d3c9a1e450"
down_revision: Union[str, Sequence[str], None] = "06933fddb519"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

INDEX_NAME = "uq_test_cases_project_tc_id"

# models.TestCase.tc_id 는 String(50)
_MAX_LEN = 50


def _fit(base: str, suffix: str = "") -> str:
    if len(base) + len(suffix) <= _MAX_LEN:
        return base + suffix
    return base[: _MAX_LEN - len(suffix)] + suffix


def _free(base: str, taken: Set[str]) -> str:
    """빈 번호를 찾는다. services/tc_id_service.allocate_tc_id 와 같은 규칙.

    마이그레이션은 자기 완결이어야 하므로 서비스 코드를 import 하지 않고 옮겨 둔다.
    """
    base = (base or "").strip() or "TC"
    candidate = _fit(base)
    if candidate not in taken:
        return candidate
    n = 2
    while True:
        candidate = _fit(base, suffix=f"-{n}")
        if candidate not in taken:
            return candidate
        n += 1


def _dedupe(bind) -> int:
    """(project_id, tc_id) 중복을 정리한다. 가장 먼저 만든 행이 원래 ID 를 유지한다."""
    groups = bind.execute(
        sa.text(
            """
            SELECT project_id, tc_id, COUNT(*) AS n
            FROM test_cases
            WHERE deleted_at IS NULL
            GROUP BY project_id, tc_id
            HAVING n > 1
            """
        )
    ).fetchall()
    if not groups:
        return 0

    renamed = 0
    for project_id, tc_id, _n in groups:
        taken = {
            r[0]
            for r in bind.execute(
                sa.text(
                    "SELECT tc_id FROM test_cases "
                    "WHERE project_id = :p AND deleted_at IS NULL"
                ),
                {"p": project_id},
            )
            if r[0]
        }
        row_ids = [
            r[0]
            for r in bind.execute(
                sa.text(
                    "SELECT id FROM test_cases "
                    "WHERE project_id = :p AND tc_id = :t AND deleted_at IS NULL "
                    "ORDER BY id"
                ),
                {"p": project_id, "t": tc_id},
            )
        ]
        # 첫 행은 그대로 두고 나머지에 번호를 붙인다
        for row_id in row_ids[1:]:
            new_id = _free(tc_id, taken)
            taken.add(new_id)
            bind.execute(
                sa.text("UPDATE test_cases SET tc_id = :new WHERE id = :i"),
                {"new": new_id, "i": row_id},
            )
            logger.warning(
                "TC ID 중복 정리: project=%s id=%s '%s' -> '%s'",
                project_id, row_id, tc_id, new_id,
            )
            renamed += 1
    return renamed


def upgrade() -> None:
    bind = op.get_bind()
    renamed = _dedupe(bind)
    if renamed:
        logger.warning(
            "TC ID 중복 %d건을 정리했다. 위 목록을 확인해 필요한 이름으로 고칠 것.",
            renamed,
        )

    op.create_index(
        INDEX_NAME,
        "test_cases",
        ["project_id", "tc_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="test_cases")
