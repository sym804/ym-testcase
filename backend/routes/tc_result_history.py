from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, TestCase, TestRun, TestResult
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/testcases",
    tags=["tc-result-history"],
)


@router.get("/{tc_id}/result-history")
def get_tc_result_history(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """특정 TC의 모든 테스트 결과를 런별로 시간순(최신 먼저) 반환."""
    tc = db.query(TestCase).filter(
        TestCase.id == tc_id,
        TestCase.project_id == project_id,
    ).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    results = (
        db.query(TestResult, TestRun)
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(
            TestResult.test_case_id == tc_id,
            TestRun.project_id == project_id,
        )
        .order_by(TestRun.created_at.desc())
        .all()
    )

    return [
        {
            "result_id": result.id,
            "result": result.result.value if hasattr(result.result, "value") else str(result.result),
            "actual_result": result.actual_result,
            "issue_link": result.issue_link,
            "remarks": result.remarks,
            "executed_at": result.executed_at.isoformat() if result.executed_at else None,
            "duration_sec": result.duration_sec,
            "run_id": run.id,
            "run_name": run.name,
            "version": run.version,
            "environment": run.environment,
            "round": run.round,
            "run_status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "run_created_at": run.created_at.isoformat() if run.created_at else None,
        }
        for result, run in results
    ]
