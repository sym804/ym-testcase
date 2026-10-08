"""수행 회차 유일성: (project_id, name, round)

추가 전에 중복을 확인한다. 있으면 멈추고 목록을 낸다. 자동으로 고치지 않는다.
어느 쪽을 남길지는 결과와 이슈가 달린 수행이라 사람이 정한다.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_unique_run_round"
down_revision = "0001_pg_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    dup = op.get_bind().execute(sa.text(
        "SELECT project_id, name, round, count(*) FROM test_runs "
        "GROUP BY project_id, name, round HAVING count(*) > 1"
    )).all()
    if dup:
        raise RuntimeError(f"같은 회차가 둘 이상인 수행이 있다. 먼저 정리한다: {[tuple(r) for r in dup]}")
    op.create_index("uq_test_runs_project_name_round", "test_runs",
                    ["project_id", "name", "round"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_test_runs_project_name_round", table_name="test_runs")
