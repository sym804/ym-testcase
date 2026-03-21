from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import User, TestCase, TestCaseHistory, ProjectMember
from schemas import TestCaseHistoryResponse
from auth import get_current_user, get_project_role

router = APIRouter(prefix="/api/history", tags=["history"])


def _check_project_member(project_id: int, user: User, db: Session):
    """프로젝트 멤버인지 확인. 접근 권한이 없으면 403 반환."""
    role = get_project_role(project_id, user, db)
    if role is None:
        raise HTTPException(status_code=403, detail="이 프로젝트에 접근 권한이 없습니다.")


@router.get("/project/{project_id}", response_model=List[TestCaseHistoryResponse])
def get_project_history(
    project_id: int,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get recent change history for all test cases in a project."""
    _check_project_member(project_id, current_user, db)
    tc_ids = (
        db.query(TestCase.id)
        .filter(TestCase.project_id == project_id)
        .subquery()
    )
    rows = (
        db.query(TestCaseHistory)
        .options(joinedload(TestCaseHistory.changer), joinedload(TestCaseHistory.test_case))
        .filter(TestCaseHistory.test_case_id.in_(tc_ids))
        .order_by(TestCaseHistory.changed_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for r in rows:
        results.append(TestCaseHistoryResponse(
            id=r.id,
            test_case_id=r.test_case_id,
            changed_by=r.changed_by,
            changer_name=r.changer.display_name if r.changer else None,
            changed_at=r.changed_at,
            field_name=r.field_name,
            old_value=r.old_value,
            new_value=r.new_value,
            tc_id=r.test_case.tc_id if r.test_case else None,
        ))
    return results


@router.get("/testcase/{test_case_id}", response_model=List[TestCaseHistoryResponse])
def get_testcase_history(
    test_case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(TestCaseHistory)
        .options(joinedload(TestCaseHistory.changer))
        .filter(TestCaseHistory.test_case_id == test_case_id)
        .order_by(TestCaseHistory.changed_at.desc())
        .limit(100)
        .all()
    )
    results = []
    for r in rows:
        results.append(TestCaseHistoryResponse(
            id=r.id,
            test_case_id=r.test_case_id,
            changed_by=r.changed_by,
            changer_name=r.changer.display_name if r.changer else None,
            changed_at=r.changed_at,
            field_name=r.field_name,
            old_value=r.old_value,
            new_value=r.new_value,
        ))
    return results
