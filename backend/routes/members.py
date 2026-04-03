import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import User, Project, ProjectMember, ProjectRole, UserRole
from schemas import ProjectMemberCreate, ProjectMemberUpdate, ProjectMemberResponse
from auth import get_current_user, check_project_access, role_required

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/members",
    tags=["project-members"],
)


@router.get("", response_model=List[ProjectMemberResponse])
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """프로젝트 멤버 목록 조회"""
    members = (
        db.query(ProjectMember)
        .options(joinedload(ProjectMember.user))
        .filter(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.added_at)
        .all()
    )
    result = []
    for m in members:
        user = m.user
        result.append(ProjectMemberResponse(
            id=m.id,
            project_id=m.project_id,
            user_id=m.user_id,
            role=m.role.value if isinstance(m.role, ProjectRole) else m.role,
            added_at=m.added_at,
            username=user.username if user else None,
            display_name=user.display_name if user else None,
        ))
    return result


@router.get("/available-users")
def list_available_users(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """멤버 추가용 사용자 목록 — 이미 멤버인 사용자 제외"""
    from schemas import UserResponse
    existing_user_ids = {m.user_id for m in db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id
    ).all()}
    users = db.query(User).filter(
        ~User.id.in_(existing_user_ids) if existing_user_ids else True
    ).order_by(User.id).all()
    return [UserResponse.model_validate(u) for u in users]


@router.post("", response_model=ProjectMemberResponse, status_code=status.HTTP_201_CREATED)
def add_member(
    project_id: int,
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """프로젝트에 멤버 추가 (프로젝트 admin만)"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # 중복 체크
    existing = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == payload.user_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")

    # 역할 검증
    valid_roles = [r.value for r in ProjectRole]
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")

    member = ProjectMember(
        project_id=project_id,
        user_id=payload.user_id,
        role=ProjectRole(payload.role),
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    logger.info(
        "Member added: project=%d user=%s role=%s by=%s",
        project_id, user.username, payload.role, current_user.username,
    )

    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role.value,
        added_at=member.added_at,
        username=user.username,
        display_name=user.display_name,
    )


@router.put("/{member_id}", response_model=ProjectMemberResponse)
def update_member_role(
    project_id: int,
    member_id: int,
    payload: ProjectMemberUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """멤버 역할 변경 (프로젝트 admin만)"""
    member = db.query(ProjectMember).filter(
        ProjectMember.id == member_id,
        ProjectMember.project_id == project_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    valid_roles = [r.value for r in ProjectRole]
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {valid_roles}")

    member.role = ProjectRole(payload.role)
    db.commit()
    db.refresh(member)

    user = db.query(User).filter(User.id == member.user_id).first()
    return ProjectMemberResponse(
        id=member.id,
        project_id=member.project_id,
        user_id=member.user_id,
        role=member.role.value,
        added_at=member.added_at,
        username=user.username if user else None,
        display_name=user.display_name if user else None,
    )


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    project_id: int,
    member_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """멤버 제거 (프로젝트 admin만)"""
    member = db.query(ProjectMember).filter(
        ProjectMember.id == member_id,
        ProjectMember.project_id == project_id,
    ).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # 프로젝트 생성자는 제거 불가
    project = db.query(Project).filter(Project.id == project_id).first()
    if project and member.user_id == project.created_by:
        raise HTTPException(status_code=400, detail="Cannot remove the project creator")

    logger.info(
        "Member removed: project=%d user_id=%d by=%s",
        project_id, member.user_id, current_user.username,
    )

    db.delete(member)
    db.commit()


# ── 전체 프로젝트 일괄 배정 / 전체 배정 조회 ──────────────────────────────────

assign_all_router = APIRouter(prefix="/api/projects", tags=["project-members"])


@assign_all_router.get("/all-assignments")
def get_all_assignments(
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("qa_manager")),
):
    """모든 프로젝트 멤버 배정 정보를 한 번에 반환 (관리자용)"""
    members = db.query(ProjectMember).all()
    projects = {p.id: p.name for p in db.query(Project).all()}
    result: dict[int, list] = {}
    for m in members:
        entry = {
            "id": m.id,
            "project_id": m.project_id,
            "project_name": projects.get(m.project_id, f"#{m.project_id}"),
            "role": m.role.value if isinstance(m.role, ProjectRole) else m.role,
        }
        result.setdefault(m.user_id, []).append(entry)
    return result


@assign_all_router.post("/assign-all")
def assign_to_all_projects(
    payload: ProjectMemberCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("qa_manager")),
):
    """사용자를 모든 프로젝트에 일괄 배정"""
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    valid_roles = [r.value for r in ProjectRole]
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 역할입니다. ({', '.join(valid_roles)})")

    all_projects = db.query(Project).all()
    project_ids = [p.id for p in all_projects]

    # 기존 배정된 프로젝트 ID를 한 번에 조회 (N+1 방지)
    existing_ids = set(
        row[0] for row in db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == payload.user_id,
            ProjectMember.project_id.in_(project_ids),
        ).all()
    ) if project_ids else set()

    assigned = 0
    for p in all_projects:
        if p.id not in existing_ids:
            db.add(ProjectMember(
                project_id=p.id,
                user_id=payload.user_id,
                role=ProjectRole(payload.role),
            ))
            assigned += 1
    db.commit()
    logger.info(
        "Bulk assign: user=%s role=%s projects=%d by=%s",
        user.username, payload.role, assigned, current_user.username,
    )
    return {"assigned": assigned, "total_projects": len(all_projects)}
