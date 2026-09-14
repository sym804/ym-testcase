from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, CustomFieldDef
from schemas import CustomFieldDefCreate, CustomFieldDefUpdate, CustomFieldDefResponse
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/custom-fields",
    tags=["custom-fields"],
)


#: 프론트의 선택지(ProjectSettings 의 FIELD_TYPE_KEYS)와 같아야 한다.
#: 값이 벗어나면 화면이 `fieldType_<값>` 을 못 찾아 raw key 를 그대로 보여 준다.
VALID_FIELD_TYPES = {"text", "number", "select", "multiselect", "checkbox", "date"}


def _validate_field_type(field_type: str) -> None:
    """★생성과 수정이 같은 검증을 쓰게 한다. 생성에만 걸려 있던 동안 수정 API 로
    임의 타입을 넣을 수 있었다(실측: PUT 으로 'EVIL_TYPE' 이 그대로 저장됨)."""
    if field_type not in VALID_FIELD_TYPES:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 필드 타입: {field_type}")


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=List[CustomFieldDefResponse])
def list_custom_fields(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    _get_project_or_404(project_id, db)
    return (
        db.query(CustomFieldDef)
        .filter(CustomFieldDef.project_id == project_id)
        .order_by(CustomFieldDef.sort_order, CustomFieldDef.id)
        .all()
    )


@router.post("", response_model=CustomFieldDefResponse, status_code=201)
def create_custom_field(
    project_id: int,
    payload: CustomFieldDefCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    name = payload.field_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="필드 이름을 입력해 주세요.")

    exists = db.query(CustomFieldDef).filter(
        CustomFieldDef.project_id == project_id, CustomFieldDef.field_name == name
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="이미 존재하는 필드 이름입니다.")

    _validate_field_type(payload.field_type)

    max_order = db.query(CustomFieldDef.sort_order).filter(
        CustomFieldDef.project_id == project_id
    ).order_by(CustomFieldDef.sort_order.desc()).first()
    next_order = (max_order[0] + 1) if max_order else 0

    field = CustomFieldDef(
        project_id=project_id,
        field_name=name,
        field_type=payload.field_type,
        options=payload.options,
        sort_order=next_order,
        is_required=payload.is_required,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


@router.put("/{field_id}", response_model=CustomFieldDefResponse)
def update_custom_field(
    project_id: int,
    field_id: int,
    payload: CustomFieldDefUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    field = db.query(CustomFieldDef).filter(
        CustomFieldDef.id == field_id, CustomFieldDef.project_id == project_id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="필드를 찾을 수 없습니다.")

    if payload.field_name is not None:
        name = payload.field_name.strip()
        if not name:
            raise HTTPException(status_code=400, detail="필드 이름을 입력해 주세요.")
        dup = db.query(CustomFieldDef).filter(
            CustomFieldDef.project_id == project_id,
            CustomFieldDef.field_name == name,
            CustomFieldDef.id != field_id,
        ).first()
        if dup:
            raise HTTPException(status_code=400, detail="이미 존재하는 필드 이름입니다.")
        field.field_name = name

    if payload.field_type is not None:
        _validate_field_type(payload.field_type)
        field.field_type = payload.field_type
    if payload.options is not None:
        field.options = payload.options
    if payload.is_required is not None:
        field.is_required = payload.is_required
    if payload.sort_order is not None:
        field.sort_order = payload.sort_order

    db.commit()
    db.refresh(field)
    return field


@router.delete("/{field_id}")
def delete_custom_field(
    project_id: int,
    field_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    field = db.query(CustomFieldDef).filter(
        CustomFieldDef.id == field_id, CustomFieldDef.project_id == project_id
    ).first()
    if not field:
        raise HTTPException(status_code=404, detail="필드를 찾을 수 없습니다.")

    db.delete(field)
    db.commit()
    return {"deleted": field.field_name}
