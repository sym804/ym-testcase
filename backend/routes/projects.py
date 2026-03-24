from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, ProjectMember, ProjectRole
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from auth import get_current_user, role_required, get_project_role, check_project_access

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_field_config(project_id: int, db: Session):
    """field_config를 raw SQL로 직접 읽는다 (SQLAlchemy JSON 캐시 우회)."""
    import json as _json
    import sqlalchemy as _sa
    result = db.execute(_sa.text("SELECT field_config FROM projects WHERE id = :pid"), {"pid": project_id})
    row = result.fetchone()
    if row and row[0]:
        try:
            return _json.loads(row[0])
        except (ValueError, TypeError):
            return None
    return None


def _project_response(project: Project, user: User, db: Session) -> dict:
    """ProjectResponse에 my_role 포함"""
    proj_role = get_project_role(project.id, user, db)
    data = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "jira_base_url": project.jira_base_url,
        "is_private": project.is_private,
        "field_config": _get_field_config(project.id, db),
        "created_by": project.created_by,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "my_role": proj_role,
    }
    return data


@router.get("", response_model=List[ProjectResponse])
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from models import UserRole as _UR
    user_role = current_user.role.value if isinstance(current_user.role, _UR) else current_user.role

    projects = db.query(Project).order_by(Project.created_at.desc()).all()

    # 멤버십 한 번에 조회 (N+1 방지)
    project_ids = [p.id for p in projects]
    memberships = {}
    if project_ids:
        rows = (
            db.query(ProjectMember.project_id, ProjectMember.role)
            .filter(
                ProjectMember.user_id == current_user.id,
                ProjectMember.project_id.in_(project_ids),
            )
            .all()
        )
        for pid, role in rows:
            memberships[pid] = role.value if isinstance(role, ProjectRole) else role

    result = []
    for p in projects:
        # 역할 결정 (get_project_role 로직 인라인)
        if user_role in ("admin", "qa_manager"):
            proj_role = "admin"
        elif p.created_by == current_user.id:
            proj_role = "admin"
        elif p.id in memberships:
            proj_role = memberships[p.id]
        elif not p.is_private:
            proj_role = "viewer"
        else:
            continue  # 접근 불가

        result.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "jira_base_url": p.jira_base_url,
            "is_private": p.is_private,
            "created_by": p.created_by,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "my_role": proj_role,
        })
    return result


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("qa_manager")),
):
    project = Project(
        name=payload.name,
        description=payload.description,
        jira_base_url=payload.jira_base_url,
        is_private=payload.is_private,
        created_by=current_user.id,
    )
    db.add(project)
    db.flush()

    # 생성자를 프로젝트 admin 멤버로 자동 추가
    member = ProjectMember(
        project_id=project.id,
        user_id=current_user.id,
        role=ProjectRole.admin,
    )
    db.add(member)
    db.commit()
    db.refresh(project)
    return _project_response(project, current_user, db)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_response(project, current_user, db)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = payload.model_dump(exclude_unset=True)

    # field_config는 JSON 문자열로 저장 (SQLite TEXT 컬럼)
    if "field_config" in update_data:
        import json as _json
        fc_val = update_data.pop("field_config")
        project.field_config = _json.dumps(fc_val, ensure_ascii=False) if fc_val else None

    for key, value in update_data.items():
        setattr(project, key, value)

    db.commit()
    db.refresh(project)
    return _project_response(project, current_user, db)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
