"""종료된 테스트 수행의 TC 내용 고정.

결과 행(`test_results`)은 TC 를 `test_case_id` 로만 가리킨다. 그래서 수행을 종료한 뒤에
TC 를 고치면 그 수행의 화면, 엑셀, 리포트가 고친 내용으로 바뀌었다. 이미 실행한 TC 라서
종료된 수행은 그때 내용으로 남아야 한다.

규칙은 하나다.
  - 진행 중인 수행은 지금 TC 를 그대로 보여 준다. 수행 도중 고친 오타는 바로 반영된다.
  - 종료하는 순간 결과 행마다 그때 TC 내용을 `tc_snapshot` 에 남긴다. 그 뒤로는 그 값을 읽는다.
  - 다시 열면(reopen) 진행 중이 되므로 고정을 푼다. 다시 종료하면 그때 내용으로 다시 남긴다.

읽는 쪽은 둘이다.
  - ORM: `TestResult.case_view` 가 고정 값이 있으면 `FrozenCase`, 없으면 지금 TC 를 준다.
  - SQL 집계: `frozen_col(필드)` 가 같은 규칙의 CASE 식을 준다.
대시보드는 쓰지 않는다. 대시보드는 수행을 골라도 지금 남은 TC 기준이다(reports.py 의
`_priority_summary_sql` 주석).
"""
from sqlalchemy import case, null
from sqlalchemy.orm import Session

from models import TestCase, TestResult, TestRunStatus

#: 고정하는 칸. TC 의 내용 칸 전부다. id, 작성자, 생성·수정 시각은 지금 TC 에서 읽는다.
#: ★시트(sheet_name)와 시트 안 순번(no)은 고정하지 않는다. TC 의 내용이 아니라 위치다.
#:   시트 이름을 바꾸면 완료된 수행의 범위(run.sheet_names)도 새 이름을 따라가는데
#:   결과만 옛 이름을 들고 있으면, 수행 화면 탭이 새 이름이라 그 결과가 걸러져 사라지고
#:   엑셀은 시트 순서를 잃는다(QA 2인 지적, 2026-11-06).
SNAPSHOT_FIELDS = (
    "tc_id", "type", "category", "depth1", "depth2", "priority", "test_type",
    "precondition", "test_steps", "expected_result", "r1", "r2", "r3", "remarks",
    "custom_fields",
)


def snapshot_of(tc: TestCase) -> dict:
    return {f: getattr(tc, f) for f in SNAPSHOT_FIELDS}


class FrozenCase:
    """고정 값을 먼저 보고, 없는 칸은 지금 TC 에서 읽는 읽기 전용 보기.

    ORM 객체가 아니라서 값을 바꿔도 DB 에 쓰이지 않는다. 쓰기는 막는다.
    """

    __slots__ = ("_live", "_snap")

    def __init__(self, live: TestCase, snap: dict):
        object.__setattr__(self, "_live", live)
        object.__setattr__(self, "_snap", snap)

    def __getattr__(self, name):
        snap = object.__getattribute__(self, "_snap")
        if name in SNAPSHOT_FIELDS and name in snap:
            return snap[name]
        return getattr(object.__getattribute__(self, "_live"), name)

    def __setattr__(self, name, value):
        raise AttributeError("종료된 수행의 TC 보기는 바꿀 수 없다")


def case_view(result: TestResult):
    tc = result.test_case
    if tc is None or not result.tc_snapshot:
        return tc
    return FrozenCase(tc, result.tc_snapshot)


def frozen_col(field: str):
    """SQL 집계용. 고정 값이 있으면 그 값, 없으면 지금 TC 칸. 문자열 칸만 쓴다."""
    if field not in SNAPSHOT_FIELDS or field == "custom_fields":
        raise ValueError(f"집계에 쓰는 문자열 칸이 아니다: {field}")
    return case(
        (TestResult.tc_snapshot.isnot(None), TestResult.tc_snapshot[field].as_string()),
        else_=getattr(TestCase, field),
    )


def frozen_tc_ids(run) -> dict:
    """종료된 수행의 {TC 행 id: 종료 시점 TC ID}. 진행 중이면 빈 dict.

    ★이슈마다 쿼리하지 않는다. 같은 세션의 이슈는 같은 TestRun 객체를 공유하므로
      run.results 는 한 번만 올라온다(예전 판은 이슈 수 x 접근 횟수만큼 SELECT 했다).
    """
    if run is None or run.status != TestRunStatus.completed:
        return {}
    return {
        r.test_case_id: r.tc_snapshot["tc_id"]
        for r in run.results
        if r.tc_snapshot and r.tc_snapshot.get("tc_id") is not None
    }


def freeze_run(run_id: int, db: Session) -> int:
    """수행의 결과 행마다 지금 TC 내용을 남긴다. 남긴 행 수를 돌려준다. 커밋은 부른 쪽이 한다.

    고정 시점은 이 SELECT 가 읽은 순간이다. 부른 쪽은 completed_at 을 먼저 정하므로,
    이 읽기 뒤에 커밋된 TC 수정은 "완료 뒤 수정" 으로 기록이 앞뒤가 맞는다. TC 행 잠금을
    더하지 않는 이유: Import 는 TC 를 고친 같은 트랜잭션에서 수행 잠금을 잡아, 여기서
    수행 잠금 -> TC 잠금 순으로 잡으면 교착이 생긴다.
    """
    rows = (
        db.query(TestResult, TestCase)
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .filter(TestResult.test_run_id == run_id)
        .all()
    )
    for result, tc in rows:
        result.tc_snapshot = snapshot_of(tc)
    return len(rows)


def unfreeze_run(run_id: int, db: Session) -> int:
    """고정을 푼다. 다시 진행 중이 된 수행은 지금 TC 를 보여 준다. 커밋은 부른 쪽이 한다."""
    return (
        db.query(TestResult)
        .filter(TestResult.test_run_id == run_id, TestResult.tc_snapshot.isnot(None))
        .update({TestResult.tc_snapshot: null()}, synchronize_session=False)
    )
