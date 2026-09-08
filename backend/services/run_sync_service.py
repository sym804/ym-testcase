"""진행 중인 테스트 런과 TC 목록의 동기화

테스트 런은 생성 시점에 프로젝트의 모든 TC에 대해 결과 행(NS)을 만든다.
그래서 런 생성 이후에 추가된 TC는 결과 행이 없어 런 그리드에서 보이지 않고,
시트 탭 배지(TC 라이브러리 기준)와 그리드 내용(런 스냅샷 기준)이 어긋난다.

진행 중인 런은 새 TC를 흡수하고, 완료된 런은 과거 기록의 무결성을 위해
생성 당시 스냅샷을 그대로 유지한다.
"""
from sqlalchemy.orm import Session

from models import TestCase, TestRun, TestResult, TestRunStatus, TestResultValue


def insert_results_ignoring_duplicates(db: Session, rows: list[dict]) -> int:
    """(test_run_id, test_case_id) 가 이미 있으면 그 행은 건너뛰고 넣는다.

    ★조회해서 없는 것만 골라 넣어도, 그 사이에 다른 요청이 같은 것을 넣을 수 있다.
      예외로 처리하면 세션 전체가 죽어 나머지 행까지 못 넣는다. DB 가 충돌 행만
      조용히 버리게 하는 편이 맞다.
    ★방언을 보고 고른다. SQLite 와 PostgreSQL 둘 다 같은 의미를 지원한다.
      PostgreSQL 전환(SYM-6) 때 이 함수만 그대로 돌면 된다.
    """
    if not rows:
        return 0
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        from sqlalchemy.dialects.postgresql import insert as _insert
    elif dialect == "sqlite":
        from sqlalchemy.dialects.sqlite import insert as _insert
    else:
        # ★모르는 방언을 SQLite 로 취급하면 조용히 틀린 SQL 을 낸다. 차라리 멈춘다.
        raise NotImplementedError(
            f"on_conflict_do_nothing 을 지원하지 않는 방언: {dialect}")
    stmt = _insert(TestResult).values(rows).on_conflict_do_nothing(
        index_elements=["test_run_id", "test_case_id"]
    )
    # ★일부 DBAPI 는 rowcount 로 -1 을 준다. 그대로 내면 호출부가 음수를 더한다.
    affected = db.execute(stmt).rowcount
    return affected if affected and affected > 0 else 0


def sync_run_results(run: TestRun, db: Session, commit: bool = True) -> int:
    """런 하나에 누락된 TC의 결과 행(NS)을 채운다.

    완료된 런은 건드리지 않는다.

    Returns: 새로 채운 행 수
    """
    if run.status != TestRunStatus.in_progress:
        return 0

    existing = db.query(TestResult.test_case_id).filter(TestResult.test_run_id == run.id).subquery()
    q = (
        db.query(TestCase.id)
        .filter(
            TestCase.project_id == run.project_id,
            TestCase.deleted_at.is_(None),
            ~TestCase.id.in_(db.query(existing.c.test_case_id)),
        )
    )
    # ★시트를 골라 만든 런은 그 범위 밖의 TC 를 흡수하면 안 된다. 저장해 둔 범위를
    #   여기서 다시 걸지 않으면, 새 TC 가 하나 생기는 순간 제외했던 시트가 통째로
    #   런에 들어온다. sheet_names 가 없는 런(옛 런 포함)은 종전대로 전체를 담는다.
    # ★빈 목록은 "전체" 가 아니라 "없음" 이다. 범위의 시트가 전부 지워진 수행이
    #   갑자기 프로젝트 전체를 담으면 안 되므로 None 인지로 가른다.
    if run.sheet_names is not None:
        q = q.filter(TestCase.sheet_name.in_(run.sheet_names))
    missing = [row[0] for row in q.order_by(TestCase.no).all()]
    if not missing:
        return 0

    # executed_by는 조회자가 아니라 런 소유자로 기록한다
    # (단순 조회 행위가 다른 사람의 실행 이력으로 남지 않도록)
    inserted = insert_results_ignoring_duplicates(db, [
        {
            "test_run_id": run.id,
            "test_case_id": tc_id,
            "result": TestResultValue.NS,
            "executed_by": run.created_by,
        }
        for tc_id in missing
    ])
    if commit:
        db.commit()
    # 다른 요청이 먼저 넣었으면 inserted 가 missing 보다 작다. 실제로 넣은 수를 낸다.
    return inserted


def sync_project_in_progress_runs(project_id: int, db: Session, commit: bool = True) -> int:
    """프로젝트의 모든 진행 중 런에 누락 TC를 반영한다.

    TC가 새로 생기는 경로(생성/복제/복원/임포트)에서 호출해, 런 상세를 열지
    않아도 대시보드·리포트가 같은 숫자를 보도록 만든다.

    Returns: 새로 채운 행 수 합계
    """
    runs = (
        db.query(TestRun)
        .filter(TestRun.project_id == project_id, TestRun.status == TestRunStatus.in_progress)
        .all()
    )
    total = 0
    for run in runs:
        total += sync_run_results(run, db, commit=False)
    if total and commit:
        db.commit()
    return total
