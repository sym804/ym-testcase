from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database import get_db
from models import User, UserRole, Project, ProjectMember, TestCase
from schemas import TestCaseResponse
from auth import get_current_user

router = APIRouter(prefix="/api/search", tags=["search"])


def _accessible_project_ids(user: User, db: Session) -> list[int]:
    """Return project IDs the user can access.

    Rules (consistent with get_project_role):
    - System admin: all projects
    - Public projects: all authenticated users
    - Private projects: members, or project creator
    """
    all_projects = db.query(Project).all()

    # System admin / qa_manager sees everything
    if user.role in (UserRole.admin, UserRole.qa_manager):
        return [p.id for p in all_projects]

    member_ids = {
        m.project_id
        for m in db.query(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user.id)
        .all()
    }

    return [
        p.id for p in all_projects
        if not p.is_private  # 공개 프로젝트는 모든 인증 사용자 접근 가능
        or p.id in member_ids
        or p.created_by == user.id
    ]


@router.get("", response_model=List[TestCaseResponse])
def global_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    accessible_ids = _accessible_project_ids(current_user, db)
    if not accessible_ids:
        return []

    pattern = f"%{q}%"
    results = (
        db.query(TestCase)
        .filter(
            TestCase.project_id.in_(accessible_ids),
            TestCase.deleted_at.is_(None),
            or_(
                TestCase.tc_id.ilike(pattern),
                TestCase.category.ilike(pattern),
                TestCase.depth1.ilike(pattern),
                TestCase.depth2.ilike(pattern),
                TestCase.test_steps.ilike(pattern),
                TestCase.expected_result.ilike(pattern),
                TestCase.precondition.ilike(pattern),
                TestCase.remarks.ilike(pattern),
            ),
        )
        .order_by(TestCase.project_id, TestCase.no)
        .limit(limit)
        .all()
    )
    return results
