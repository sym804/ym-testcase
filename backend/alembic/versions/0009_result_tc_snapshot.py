"""종료된 수행의 TC 내용 고정: test_results.tc_snapshot

수행을 종료하면 결과 행마다 그때 TC 내용을 남긴다(services/tc_snapshot.py).

이미 종료된 수행은 지금 TC 내용으로 채운다. 2026-11-06 실데이터에서 종료 뒤 바뀐 TC 는
2개 수행 98개였고, 바뀐 칸은 우선순위 용어 일괄 변경('중간' -> '보통', SYM-128) 하나뿐이었다.
내용 수정이 아니라 용어 변경이라 지금 값으로 채워도 종료 시점 내용과 같다.
다른 DB 에서는 종료 뒤 고친 내용이 그대로 들어간다. 변경 이력(test_case_history)이
Import 덮어쓰기와 시트 이동을 남기지 않아 종료 시점을 정확히 되살릴 수 없기 때문이다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_result_tc_snapshot"
down_revision = "0008_google_email"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("test_results", sa.Column("tc_snapshot", sa.JSON(), nullable=True))
    op.execute(
        """
        UPDATE test_results r
        SET tc_snapshot = json_build_object(
            'tc_id', c.tc_id, 'type', c.type, 'category', c.category,
            'depth1', c.depth1, 'depth2', c.depth2, 'priority', c.priority,
            'test_type', c.test_type, 'precondition', c.precondition,
            'test_steps', c.test_steps, 'expected_result', c.expected_result,
            'r1', c.r1, 'r2', c.r2, 'r3', c.r3, 'remarks', c.remarks,
            'custom_fields', c.custom_fields
        )
        FROM test_cases c, test_runs t
        WHERE c.id = r.test_case_id AND t.id = r.test_run_id AND t.status = 'completed'
        """
    )


def downgrade() -> None:
    op.drop_column("test_results", "tc_snapshot")
