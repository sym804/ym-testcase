"""test_cases.no 를 시트 안 1..N 으로 되돌린다

Revision ID: f2b7c04e91a8
Revises: e5a83f21c760
Create Date: 2026-09-09 00:00:00.000000

`no` 는 시트 안 순번이다. 신규 행 추가와 엑셀 임포트는 그렇게 붙이는데 복제만
프로젝트 전체 max(no)+1 을 줘서(SYM-42) 시트 안 번호에 구멍이 생겼다. 실측에서
23개 시트 중 13개가 max(no) 와 TC 수가 어긋나 있었다.

살아 있는 TC 를 지금 순서 그대로 1..N 으로 다시 매긴다. 순서를 바꾸지 않으므로
화면에 보이는 차례는 그대로고 번호만 촘촘해진다.

지운 TC 는 살아 있는 번호 뒤로 민다. 그 자리에 두면 되살릴 때 살아 있는 TC 와
번호가 겹친다.

수행 화면과 두 엑셀의 No 는 목록 순번이라 이 변경이 보이지 않는다. 달라지는 것은
TC 관리 화면의 No 컬럼과 TC 목록 엑셀이다.

★바꾸기 전 번호를 `_tc_no_backup_f2b7c04e91a8` 테이블에 남긴다. 되돌릴 수 없는
  변경이라 대조할 것을 두는 것이다. 이 테이블은 모델에 없으므로
  `alembic revision --autogenerate` 를 돌리면 drop_table 이 자동으로 생성된다.
  그 줄이 나오면 지우고 커밋해라.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b7c04e91a8"
down_revision: Union[str, Sequence[str], None] = "e5a83f21c760"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


#: 살아 있는 것 먼저, 그 안에서는 지금 번호 순. 같은 번호면 만들어진 차례.
_ORDER = "CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END, no, id"


def normalize(conn) -> None:
    """(project_id, sheet_name) 마다 no 를 1 부터 다시 매긴다.

    함수로 빼 둔다. 마이그레이션 파일 안에만 두면 테스트가 부를 수 없어서, 이
    로직이 맞는지 확인할 방법이 없어진다.
    """
    from sqlalchemy import text

    # ★순위를 CTE 로 두지 않고 임시 테이블에 먼저 담는다. 갱신 대상과 같은 테이블을
    #   읽는 CTE 는 SQLite 가 인라인으로 펼치면 행마다 다시 평가되어, 이미 바꾼 값
    #   위에서 순위를 매기게 된다. materialize 여부는 최적화기 판단이라 버전에 따라
    #   달라진다. `MATERIALIZED` 키워드는 3.35 부터라 배포 환경을 가릴 수 있어 쓰지
    #   않는다.
    conn.execute(text(f"""
        CREATE TEMP TABLE _tc_rank AS
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY project_id, sheet_name
                   ORDER BY {_ORDER}
               ) AS rn
        FROM test_cases
    """))
    # 되돌릴 수 없는 변경이다. 바꾸기 전 번호를 남겨 둔다. 이 테이블은 지우지
    # 않으므로, 나중에 무엇이 어떻게 바뀌었는지 대조할 수 있다.
    conn.execute(text(
        "CREATE TABLE IF NOT EXISTS _tc_no_backup_f2b7c04e91a8 AS "
        "SELECT id, project_id, sheet_name, no FROM test_cases"
    ))
    conn.execute(text("""
        UPDATE test_cases
        SET no = (SELECT rn FROM _tc_rank WHERE _tc_rank.id = test_cases.id)
        WHERE EXISTS (SELECT 1 FROM _tc_rank WHERE _tc_rank.id = test_cases.id)
    """))
    conn.execute(text("DROP TABLE temp._tc_rank"))


def upgrade() -> None:
    normalize(op.get_bind())


def downgrade() -> None:
    # 되돌릴 수 없다. 어떤 번호였는지 남겨 두지 않았고, 되돌릴 값어치도 없다.
    pass
