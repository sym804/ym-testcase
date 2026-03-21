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

    valid_types = {"text", "number", "select", "multiselect", "checkbox", "date"}
    if payload.field_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"유효하지 않은 필드 타입: {payload.field_type}")

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
