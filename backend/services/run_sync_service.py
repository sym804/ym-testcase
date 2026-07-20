"""진행 중인 테스트 런과 TC 목록의 동기화

테스트 런은 생성 시점에 프로젝트의 모든 TC에 대해 결과 행(NS)을 만든다.
그래서 런 생성 이후에 추가된 TC는 결과 행이 없어 런 그리드에서 보이지 않고,
시트 탭 배지(TC 라이브러리 기준)와 그리드 내용(런 스냅샷 기준)이 어긋난다.

진행 중인 런은 새 TC를 흡수하고, 완료된 런은 과거 기록의 무결성을 위해
생성 당시 스냅샷을 그대로 유지한다.
"""
from sqlalchemy.orm import Session

from models import TestCase, TestRun, TestResult, TestRunStatus, TestResultValue


def sync_run_results(run: TestRun, db: Session, commit: bool = True) -> int:
    """런 하나에 누락된 TC의 결과 행(NS)을 채운다.

    완료된 런은 건드리지 않는다.

    Returns: 새로 채운 행 수
    """
    if run.status != TestRunStatus.in_progress:
        return 0

    existing = db.query(TestResult.test_case_id).filter(TestResult.test_run_id == run.id).subquery()
    missing = [
        row[0] for row in db.query(TestCase.id)
        .filter(
            TestCase.project_id == run.project_id,
            TestCase.deleted_at.is_(None),
            ~TestCase.id.in_(db.query(existing.c.test_case_id)),
        )
        .order_by(TestCase.no)
        .all()
    ]
    if not missing:
        return 0

    # executed_by는 조회자가 아니라 런 소유자로 기록한다
    # (단순 조회 행위가 다른 사람의 실행 이력으로 남지 않도록)
    db.bulk_insert_mappings(TestResult, [
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
    return len(missing)


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
