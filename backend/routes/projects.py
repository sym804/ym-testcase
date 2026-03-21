from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, ProjectMember, ProjectRole
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from auth import get_current_user, role_required, get_project_role, check_project_access

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _project_response(project: Project, user: User, db: Session) -> dict:
    """ProjectResponse에 my_role 포함"""
    proj_role = get_project_role(project.id, user, db)
    data = {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "jira_base_url": project.jira_base_url,
        "is_private": project.is_private,
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
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    result = []
    for p in projects:
        proj_role = get_project_role(p.id, current_user, db)
        # 프로젝트에 접근 권한이 없으면 목록에서 제외
        if proj_role is None:
            continue
        result.append(_project_response(p, current_user, db))
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
