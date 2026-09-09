"""시트 안 번호를 규약대로 되돌린다.

규약: 살아 있는 TC 의 `no` 는 그 시트 안에서 유일하고, 임포트나 시트 이동이 끝나면
1 부터 이어진다. (TC 를 지우면 그 자리에 구멍이 남는다. 되살릴 수 있어야 해서
지울 때는 다시 매기지 않는다.)

번호를 넣는 길이 넷이다(신규 생성, 복제, 임포트, 드래그 정렬). 앞의 셋은 서버가
번호를 정하지만 임포트는 파일이 들고 온 값을 순서로만 쓰므로, 끝나고 한 번 훑는다.

★`uq_test_cases_sheet_no` 가 살아 있는 행에 걸려 있고 SQLite 는 행 단위로 검사한다.
  그래서 번호를 옮기는 모든 곳이 "어떤 중간 상태에서도 두 행이 같은 번호를 갖지
  않는다" 를 지켜야 한다. 여기서는 한 번 비켜 둔 뒤 최종 값을 쓴다.

★마이그레이션(f2b7c04e91a8)에도 비슷한 SQL 이 있다. 일부러 나눠 둔다. 마이그레이션은
  그때의 스키마에 묶인 기록이라, 이 파일이 바뀐다고 과거 마이그레이션까지 바뀌면
  안 된다(그 시점에는 유니크 인덱스도 없었다).
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

#: 번호를 잠시 비켜 둘 자리. 실제 번호와 겹치지 않을 만큼 낮게 둔다.
_PARK = 1000000

#: 살아 있는 것 먼저. 그 안에서는 양수(이번에 다룬 행)가 앞이고 음수(비켜 둔 채로
#: 남은 행)가 뒤다. 음수는 절대값이 원래 차례이므로 그 순서를 지킨다.
_ORDER = (
    "CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END,"
    " CASE WHEN no < 0 THEN 1 ELSE 0 END,"
    " CASE WHEN no < 0 THEN -no ELSE no END,"
    " id"
)


def park_sheet_numbers(project_id: int, sheet_name: str, db: Session) -> None:
    """그 시트의 살아 있는 번호를 음수로 비켜 둔다.

    임포트처럼 1 부터 다시 번호를 붙여 들어오는 작업 앞에 쓴다. 비켜 두지 않으면
    파일이 붙인 1..N 이 그 시트에 이미 있는 1..N 과 부딪친다.

    부호만 뒤집으므로 원래 차례가 절대값에 남는다. `_ORDER` 가 그것을 읽는다.
    """
    db.execute(
        text(
            "UPDATE test_cases SET no = -no "
            "WHERE project_id = :pid AND sheet_name = :sheet "
            "AND deleted_at IS NULL AND no > 0"
        ),
        {"pid": project_id, "sheet": sheet_name},
    )


def renumber_sheet(project_id: int, sheet_name: str, db: Session) -> None:
    """한 시트의 no 를 1 부터 다시 매긴다. 지금 차례는 바꾸지 않는다."""
    db.execute(text("DROP TABLE IF EXISTS temp._tc_rank"))
    # ★순위를 CTE 로 두지 않고 임시 테이블에 담는다. 갱신 대상과 같은 테이블을 읽는
    #   CTE 는 SQLite 가 인라인으로 펼치면 행마다 다시 평가되어, 이미 바꾼 값 위에서
    #   순위를 매기게 된다. materialize 여부는 최적화기 판단이라 버전에 따라 달라진다.
    #   `MATERIALIZED` 키워드는 3.35 부터라 배포 환경을 가릴 수 있어 쓰지 않는다.
    db.execute(
        text(f"""
            CREATE TEMP TABLE _tc_rank AS
            SELECT id, ROW_NUMBER() OVER (ORDER BY {_ORDER}) AS rn
            FROM test_cases
            WHERE project_id = :pid AND sheet_name = :sheet
        """),
        {"pid": project_id, "sheet": sheet_name},
    )
    # ★한 문장으로 바로 쓰면 안 된다. UPDATE 에는 순서가 없어서, 목표 번호를 이미
    #   다른 행이 쥐고 있는 상태에서 쓰게 되면 유니크 제약에 걸린다. 먼저 전부
    #   비켜 두고 그 다음에 쓴다.
    db.execute(text("""
        UPDATE test_cases
        SET no = -:park - (SELECT rn FROM _tc_rank WHERE _tc_rank.id = test_cases.id)
        WHERE EXISTS (SELECT 1 FROM _tc_rank WHERE _tc_rank.id = test_cases.id)
    """), {"park": _PARK})
    db.execute(text("""
        UPDATE test_cases
        SET no = (SELECT rn FROM _tc_rank WHERE _tc_rank.id = test_cases.id)
        WHERE EXISTS (SELECT 1 FROM _tc_rank WHERE _tc_rank.id = test_cases.id)
    """))
    db.execute(text("DROP TABLE temp._tc_rank"))
