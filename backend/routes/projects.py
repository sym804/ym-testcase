import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from routes.attachments import run_object_deletions, schedule_object_deletions
from models import User, Project, ProjectMember, ProjectOrder, ProjectRole, TestRun, TestResult, Attachment
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from auth import SESSION_ONLY_DETAIL, get_current_user, get_project_role, check_project_access
from services.locks import LockNs, advisory_xact_lock
from services.project_order import ordered

logger = logging.getLogger(__name__)

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
        "issue_tracker": project.issue_tracker,
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

    # 메인 화면과 같은 사용자별 순서(SYM-228). 상단 프로젝트 선택 목록이 이 순서를 쓴다.
    projects = ordered(db.query(Project), current_user.id).all()

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
            "issue_tracker": p.issue_tracker,
            "is_private": p.is_private,
            "created_by": p.created_by,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "my_role": proj_role,
        })
    return result


ORDER_UNKNOWN_DETAIL = "볼 수 없거나 없는 프로젝트가 들어 있습니다. 목록을 새로고침한 뒤 다시 옮겨 주세요."
ORDER_DUPLICATE_DETAIL = "같은 프로젝트가 두 번 들어 있습니다."


class ProjectOrderUpdate(BaseModel):
    #: 위에서 아래 순서. 빠진 프로젝트는 순서를 정하지 않은 것으로 돌아가 맨 위에 놓인다.
    project_ids: List[int] = Field(..., max_length=2000)


@router.put("/order", status_code=status.HTTP_204_NO_CONTENT)
def update_project_order(
    payload: ProjectOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """메인 화면 프로젝트 순서 저장 (SYM-228). 내 화면에만 적용된다.

    ★/{project_id} 경로보다 먼저 등록한다. 뒤에 두면 "order" 가 project_id 로 잡혀 422 가 난다.
    """
    from routes.overview import visible_projects

    ids = payload.project_ids
    if len(set(ids)) != len(ids):
        raise HTTPException(status_code=400, detail=ORDER_DUPLICATE_DETAIL)
    # 없는 프로젝트와 볼 수 없는 비공개 프로젝트를 같은 문구로 거절한다(존재 여부를 알리지 않는다).
    visible = {p.id for p in visible_projects(db, current_user)}
    if not set(ids) <= visible:
        raise HTTPException(status_code=400, detail=ORDER_UNKNOWN_DETAIL)
    # 두 탭에서 동시에 저장하면 지우고 넣는 사이가 겹쳐 PK 충돌이 난다. 사용자 단위로 줄 세운다.
    advisory_xact_lock(db, LockNs.PROJECT_ORDER, current_user.id)
    db.query(ProjectOrder).filter(ProjectOrder.user_id == current_user.id).delete(synchronize_session=False)
    db.add_all(ProjectOrder(user_id=current_user.id, project_id=pid, position=i) for i, pid in enumerate(ids))
    try:
        db.commit()
    except IntegrityError:
        # 확인과 저장 사이에 다른 사람이 프로젝트를 지웠다. 전역 처리기의 "데이터 제약 조건"(409)
        # 대신 새로고침 안내를 준다. 롤백하므로 앞의 순서가 그대로 남는다.
        db.rollback()
        raise HTTPException(status_code=400, detail=ORDER_UNKNOWN_DETAIL)


PUBLIC_BY_KEY_DETAIL = "API 키로는 공개 프로젝트를 만들 수 없습니다. is_private 를 true 로 보내거나 로그인해서 진행해 주세요."


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ★API 키로는 비공개 프로젝트만 만든다(SYM-217, QA1 지적). 관리자 키로 남의 비공개 TC 를 내보내
    #   공개 프로젝트에 가져오면 공개 전환(update_project 에서 막음)과 같은 일이 된다.
    if not payload.is_private and getattr(request.state, "auth_method", None) == "api_key":
        raise HTTPException(status_code=403, detail=PUBLIC_BY_KEY_DETAIL)
    # 로그인한 사용자는 누구나 만든다. 만든 사람은 그 프로젝트의 admin 멤버가 되고,
    # 다른 프로젝트에 대한 권한은 멤버 표로만 정해지므로 넓어지지 않는다.
    # 프로젝트 admin 이면 열리는 전역 정보(멤버 후보 목록)는 최소 칸만 준다(members.py).
    project = Project(
        name=payload.name,
        description=payload.description,
        jira_base_url=payload.jira_base_url,
        issue_tracker=payload.issue_tracker,
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
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = payload.model_dump(exclude_unset=True)
    # ★공개 범위 변경은 API 키로 받지 않는다(SYM-217, QA1 지적). 시스템 관리자는 모든 프로젝트의
    #   admin 이라 관리자 키로 프로젝트마다 공개로 바꾸면 비멤버 전원에게 열리고, 키를 폐기해도 남는다.
    #   이름·설명 같은 다른 칸은 키로도 고친다.
    if ("is_private" in update_data and update_data["is_private"] != project.is_private
            and getattr(request.state, "auth_method", None) == "api_key"):
        raise HTTPException(status_code=403, detail=SESSION_ONLY_DETAIL)

    # field_config는 JSON 문자열로 저장 (Text 컬럼, 읽을 때 json.loads)
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

    # 프로젝트에 속한 첨부파일 실파일 삭제. 키는 지금 모으고 저장소는 커밋 뒤에 지운다
    # (schedule_object_deletions 참고).
    pending = []
    run_ids = [r.id for r in db.query(TestRun.id).filter(TestRun.project_id == project_id).all()]
    if run_ids:
        result_ids = [r.id for r in db.query(TestResult.id).filter(TestResult.test_run_id.in_(run_ids)).all()]
        if result_ids:
            attachments = db.query(Attachment).filter(Attachment.test_result_id.in_(result_ids)).all()
            pending = schedule_object_deletions([att.filepath for att in attachments], db)

    db.delete(project)
    db.commit()
    run_object_deletions(pending, db)
