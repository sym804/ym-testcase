from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, SavedFilter, TestCase
from schemas import SavedFilterCreate, SavedFilterUpdate, SavedFilterResponse
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/filters",
    tags=["filters"],
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=List[SavedFilterResponse])
def list_filters(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    _get_project_or_404(project_id, db)
    return (
        db.query(SavedFilter)
        .filter(SavedFilter.project_id == project_id)
        .order_by(SavedFilter.created_at.desc())
        .all()
    )


@router.post("", response_model=SavedFilterResponse, status_code=201)
def create_filter(
    project_id: int,
    payload: SavedFilterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="필터 이름을 입력해 주세요.")

    if payload.logic not in ("AND", "OR"):
        raise HTTPException(status_code=400, detail="logic은 AND 또는 OR이어야 합니다.")

    f = SavedFilter(
        project_id=project_id,
        name=name,
        conditions=[c.model_dump() for c in payload.conditions],
        logic=payload.logic,
        created_by=current_user.id,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.put("/{filter_id}", response_model=SavedFilterResponse)
def update_filter(
    project_id: int,
    filter_id: int,
    payload: SavedFilterUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    f = db.query(SavedFilter).filter(
        SavedFilter.id == filter_id, SavedFilter.project_id == project_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="필터를 찾을 수 없습니다.")

    if payload.name is not None:
        f.name = payload.name.strip()
    if payload.conditions is not None:
        f.conditions = [c.model_dump() for c in payload.conditions]
    if payload.logic is not None:
        if payload.logic not in ("AND", "OR"):
            raise HTTPException(status_code=400, detail="logic은 AND 또는 OR이어야 합니다.")
        f.logic = payload.logic

    db.commit()
    db.refresh(f)
    return f


@router.delete("/{filter_id}")
def delete_filter(
    project_id: int,
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    f = db.query(SavedFilter).filter(
        SavedFilter.id == filter_id, SavedFilter.project_id == project_id
    ).first()
    if not f:
        raise HTTPException(status_code=404, detail="필터를 찾을 수 없습니다.")

    db.delete(f)
    db.commit()
    return {"deleted": f.name}


# ── 고급 필터 적용 (TC 조회) ─────────────────────────────────────────────────

VALID_FIELDS = {
    "tc_id", "type", "category", "depth1", "depth2", "priority",
    "test_type", "precondition", "test_steps", "expected_result",
    "remarks", "sheet_name", "no",
}


#: 정수 칸. 문자열 연산(포함/빈 값)이 의미가 없고 값은 정수로 바꿔 비교한다.
#: SQLite 는 타입을 섞어도 넘어갔지만 PostgreSQL 은 연산자 오류로 500 을 낸다.
INT_FIELDS = {"no"}
_INT_OPERATORS = {"eq", "neq", "gt", "lt", "gte", "lte", "in"}


#: PostgreSQL INTEGER 범위. 넘는 값은 비교 전에 거절한다(DB 오류로 500 이 나지 않게).
_INT_MIN, _INT_MAX = -(2 ** 31), 2 ** 31 - 1


def _to_int(value):
    def bad():
        return HTTPException(status_code=400, detail=f"숫자 칸에는 정수만 쓸 수 있습니다: {value!r}")
    if isinstance(value, bool):
        raise bad()
    if isinstance(value, int):
        n = value
    else:
        s = str(value).strip() if value is not None else ""
        # isdigit 은 '²' 같은 문자도 숫자로 본다. ASCII 숫자만 받는다.
        if not s or len(s) > 11 or not all(c in "0123456789" for c in s.lstrip("-")) or s.count("-") > 1:
            raise bad()
        try:
            n = int(s)
        except ValueError:
            raise bad()
    if not (_INT_MIN <= n <= _INT_MAX):
        raise bad()
    return n


def _apply_condition(q, field: str, operator: str, value):
    """단일 조건을 쿼리에 적용"""
    if field not in VALID_FIELDS:
        return q

    col = getattr(TestCase, field, None)
    if col is None:
        return q

    if field in INT_FIELDS:
        if operator not in _INT_OPERATORS:
            raise HTTPException(status_code=400, detail=f"숫자 칸에는 '{operator}' 조건을 쓸 수 없습니다")
        if operator == "in":
            # ★리스트가 아니면 조건이 조용히 빠져, OR 묶음에서는 결과가 전체로 넓어진다.
            if not isinstance(value, list):
                raise HTTPException(status_code=400, detail="'in' 조건에는 목록을 줍니다")
            value = [_to_int(v) for v in value]
        else:
            value = _to_int(value)
    elif operator == "in":
        if not isinstance(value, list):
            raise HTTPException(status_code=400, detail="'in' 조건에는 목록을 줍니다")
        value = [str(v) for v in value]
    elif value is not None and not isinstance(value, str):
        # 문자열 칸에 숫자를 주면 PostgreSQL 은 varchar = integer 로 500 을 낸다.
        value = str(value)

    if operator == "eq":
        return q.filter(col == value)
    elif operator == "neq":
        return q.filter(col != value)
    elif operator == "contains":
        return q.filter(col.ilike(f"%{value}%"))
    elif operator == "not_contains":
        return q.filter(~col.ilike(f"%{value}%"))
    elif operator == "gt":
        return q.filter(col > value)
    elif operator == "lt":
        return q.filter(col < value)
    elif operator == "gte":
        return q.filter(col >= value)
    elif operator == "lte":
        return q.filter(col <= value)
    elif operator == "in":
        if isinstance(value, list):
            return q.filter(col.in_(value))
    elif operator == "empty":
        return q.filter((col.is_(None)) | (col == ""))
    elif operator == "not_empty":
        return q.filter(col.isnot(None), col != "")

    return q


@router.post("/apply")
def apply_filter(
    project_id: int,
    payload: SavedFilterCreate,
    sheet_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """필터 조건을 적용하여 TC 목록을 반환한다 (저장 없이 즉시 적용)."""
    _get_project_or_404(project_id, db)

    q = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    )
    if sheet_name:
        q = q.filter(TestCase.sheet_name == sheet_name)

    from sqlalchemy import or_, and_

    if payload.logic == "OR":
        or_conditions = []
        for cond in payload.conditions:
            sub_q = db.query(TestCase.id).filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
            )
            sub_q = _apply_condition(sub_q, cond.field, cond.operator, cond.value)
            or_conditions.append(TestCase.id.in_(sub_q))
        if or_conditions:
            q = q.filter(or_(*or_conditions))
    else:  # AND
        for cond in payload.conditions:
            q = _apply_condition(q, cond.field, cond.operator, cond.value)

    from schemas import TestCaseResponse
    return [TestCaseResponse.model_validate(tc) for tc in q.order_by(TestCase.no).all()]
