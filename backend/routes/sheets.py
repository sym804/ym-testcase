from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, TestCase, TestCaseSheet, now_kst
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/testcases",
    tags=["sheets"],
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _build_sheet_tree(sheets, tc_counts):
    """flat 시트 리스트를 트리 구조로 변환"""
    node_map = {}
    for s in sheets:
        node_map[s.id] = {
            "id": s.id,
            "name": s.name,
            "parent_id": s.parent_id,
            "sort_order": s.sort_order,
            "is_folder": getattr(s, "is_folder", False),
            "tc_count": tc_counts.get(s.name, 0),
            "children": [],
        }

    roots = []
    for s in sheets:
        node = node_map[s.id]
        if s.parent_id and s.parent_id in node_map:
            node_map[s.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


def _collect_descendant_names(sheet_id: int, db: Session, project_id: int) -> list[str]:
    """시트와 모든 하위 시트의 이름 목록 반환 (1회 DB 조회)"""
    # 전체 시트를 한 번에 로드 후 메모리에서 트리 탐색
    all_sheets = db.query(TestCaseSheet).filter(
        TestCaseSheet.project_id == project_id
    ).all()
    sheet_map = {s.id: s for s in all_sheets}
    children_map: dict[int, list] = {}
    for s in all_sheets:
        if s.parent_id is not None:
            children_map.setdefault(s.parent_id, []).append(s.id)

    names = []
    stack = [sheet_id]
    while stack:
        sid = stack.pop()
        s = sheet_map.get(sid)
        if s:
            names.append(s.name)
            stack.extend(children_map.get(sid, []))
    return names


@router.get("/sheets")
def list_sheets(
    project_id: int,
    flat: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """프로젝트의 시트 목록을 트리 구조로 반환한다. ?flat=true 시 기존 flat 포맷."""
    _get_project_or_404(project_id, db)

    # DB에 등록된 시트 목록
    registered = (
        db.query(TestCaseSheet)
        .filter(TestCaseSheet.project_id == project_id)
        .order_by(TestCaseSheet.sort_order, TestCaseSheet.id)
        .all()
    )

    # TC 기준 시트별 카운트
    tc_counts = dict(
        db.query(TestCase.sheet_name, func.count(TestCase.id))
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
        .group_by(TestCase.sheet_name)
        .all()
    )

    if not registered:
        # 시트 테이블이 비어있으면 TC 기반으로 반환 (기존 호환)
        if not tc_counts:
            return []
        rows = (
            db.query(TestCase.sheet_name, func.count(TestCase.id), func.min(TestCase.id))
            .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
            .group_by(TestCase.sheet_name)
            .order_by(func.min(TestCase.id))
            .all()
        )
        return [{"id": 0, "name": name or "기본", "parent_id": None, "sort_order": i, "tc_count": cnt, "children": []} for i, (name, cnt, _) in enumerate(rows)]

    # flat=true: 기존 호환 포맷
    if flat == "true":
        result = [{"name": s.name, "tc_count": tc_counts.get(s.name, 0)} for s in registered]
        registered_names = {s.name for s in registered}
        for name, cnt in tc_counts.items():
            if name and name not in registered_names:
                result.append({"name": name, "tc_count": cnt})
        return result

    # 트리 구조 반환
    tree = _build_sheet_tree(registered, tc_counts)

    # 등록 안 된 시트가 TC에 존재하면 root에 추가 (호환성)
    registered_names = {s.name for s in registered}
    for name, cnt in tc_counts.items():
        if name and name not in registered_names:
            tree.append({"id": 0, "name": name, "parent_id": None, "sort_order": 999, "tc_count": cnt, "children": []})

    return tree


class _SheetCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    is_folder: bool = False


@router.post("/sheets")
def create_sheet(
    project_id: int,
    payload: _SheetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """빈 시트를 생성한다. parent_id로 부모 시트 지정 가능."""
    _get_project_or_404(project_id, db)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="시트 이름을 입력해 주세요.")

    exists = db.query(TestCaseSheet).filter(
        TestCaseSheet.project_id == project_id, TestCaseSheet.name == name
    ).first()
    if exists:
        raise HTTPException(status_code=400, detail="이미 존재하는 시트 이름입니다.")

    # parent_id 유효성 검증
    if payload.parent_id is not None:
        parent = db.query(TestCaseSheet).filter(
            TestCaseSheet.id == payload.parent_id, TestCaseSheet.project_id == project_id
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="부모 시트를 찾을 수 없습니다.")
        # 부모가 일반 시트면 자동으로 폴더로 승격
        if not parent.is_folder:
            parent.is_folder = True

    # 같은 부모 아래에서 최대 sort_order
    sibling_q = db.query(TestCaseSheet.sort_order).filter(
        TestCaseSheet.project_id == project_id,
        TestCaseSheet.parent_id == payload.parent_id,
    )
    max_order = sibling_q.order_by(TestCaseSheet.sort_order.desc()).first()
    next_order = (max_order[0] + 1) if max_order else 0

    sheet = TestCaseSheet(project_id=project_id, name=name, sort_order=next_order, parent_id=payload.parent_id, is_folder=payload.is_folder)
    db.add(sheet)
    db.commit()
    db.refresh(sheet)
    return {"id": sheet.id, "name": sheet.name, "parent_id": sheet.parent_id, "sort_order": sheet.sort_order, "is_folder": sheet.is_folder, "tc_count": 0, "children": []}


class _SheetRename(BaseModel):
    new_name: str


@router.put("/sheets/{sheet_id}/rename")
def rename_sheet(
    project_id: int,
    sheet_id: int,
    payload: _SheetRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """시트 이름을 변경한다."""
    _get_project_or_404(project_id, db)

    sheet = db.query(TestCaseSheet).filter(
        TestCaseSheet.id == sheet_id, TestCaseSheet.project_id == project_id
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="시트를 찾을 수 없습니다.")

    new_name = payload.new_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="시트 이름을 입력해 주세요.")

    dup = db.query(TestCaseSheet).filter(
        TestCaseSheet.project_id == project_id, TestCaseSheet.name == new_name, TestCaseSheet.id != sheet_id
    ).first()
    if dup:
        raise HTTPException(status_code=400, detail="이미 존재하는 시트 이름입니다.")

    old_name = sheet.name
    sheet.name = new_name

    # TC의 sheet_name도 업데이트
    db.query(TestCase).filter(
        TestCase.project_id == project_id, TestCase.sheet_name == old_name
    ).update({TestCase.sheet_name: new_name}, synchronize_session="fetch")

    db.commit()
    return {"id": sheet.id, "name": sheet.name, "old_name": old_name}


class _SheetMove(BaseModel):
    parent_id: Optional[int] = None
    sort_order: Optional[int] = None


@router.put("/sheets/{sheet_id}/move")
def move_sheet(
    project_id: int,
    sheet_id: int,
    payload: _SheetMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """시트를 다른 부모 아래로 이동하거나 순서를 변경한다."""
    _get_project_or_404(project_id, db)

    sheet = db.query(TestCaseSheet).filter(
        TestCaseSheet.id == sheet_id, TestCaseSheet.project_id == project_id
    ).first()
    if not sheet:
        raise HTTPException(status_code=404, detail="시트를 찾을 수 없습니다.")

    # 자기 자신이나 자손을 부모로 설정하면 순환 참조
    if payload.parent_id is not None:
        if payload.parent_id == sheet_id:
            raise HTTPException(status_code=400, detail="자기 자신을 부모로 설정할 수 없습니다.")
        desc_names = _collect_descendant_names(sheet_id, db, project_id)
        parent = db.query(TestCaseSheet).filter(
            TestCaseSheet.id == payload.parent_id, TestCaseSheet.project_id == project_id
        ).first()
        if not parent:
            raise HTTPException(status_code=400, detail="부모 시트를 찾을 수 없습니다.")
        if parent.name in desc_names:
            raise HTTPException(status_code=400, detail="하위 시트를 부모로 설정할 수 없습니다.")

    sheet.parent_id = payload.parent_id
    if payload.sort_order is not None:
        sheet.sort_order = payload.sort_order
    db.commit()
    return {"id": sheet.id, "name": sheet.name, "parent_id": sheet.parent_id, "sort_order": sheet.sort_order}


@router.delete("/sheets/{sheet_name}")
def delete_sheet(
    project_id: int,
    sheet_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """시트와 속한 모든 TC를 삭제한다. 하위 시트도 함께 삭제."""
    _get_project_or_404(project_id, db)
    now = now_kst()

    # 시트 찾기
    sheet = db.query(TestCaseSheet).filter(
        TestCaseSheet.project_id == project_id, TestCaseSheet.name == sheet_name
    ).first()

    if sheet:
        # 하위 시트 포함 모든 이름 수집
        all_names = _collect_descendant_names(sheet.id, db, project_id)
    else:
        all_names = [sheet_name]

    # TC 소프트 삭제 (모든 하위 시트 포함)
    count = 0
    for name in all_names:
        c = (
            db.query(TestCase)
            .filter(TestCase.project_id == project_id, TestCase.sheet_name == name, TestCase.deleted_at.is_(None))
            .update({TestCase.deleted_at: now}, synchronize_session="fetch")
        )
        count += c

    # 시트 레코드 삭제 (하위 시트 포함, leaf부터 역순 삭제)
    if sheet:
        # 모든 하위 시트 ID 수집 후 역순 삭제 (leaf first)
        all_ids = []
        stack = [sheet.id]
        while stack:
            sid = stack.pop()
            all_ids.append(sid)
            children = db.query(TestCaseSheet).filter(
                TestCaseSheet.parent_id == sid, TestCaseSheet.project_id == project_id
            ).all()
            stack.extend(c.id for c in children)
        for sid in reversed(all_ids):
            db.query(TestCaseSheet).filter(TestCaseSheet.id == sid).delete()

    db.commit()
    return {"deleted": count, "sheet": sheet_name}


# ── 시트 무결성 검증 ─────────────────────────────────────────────────────────

def _validate_sheet_name(project_id: int, sheet_name: str | None, db: Session, *, auto_create_default: bool = False):
    """시트 이름 유효성 검증: 폴더 직접 추가 금지, 존재하지 않는 시트 금지.
    auto_create_default=True이면 "기본" 시트가 없을 때 자동 생성."""
    if not sheet_name:
        return
    sheet = db.query(TestCaseSheet).filter(
        TestCaseSheet.project_id == project_id,
        TestCaseSheet.name == sheet_name,
    ).first()
    if not sheet:
        if auto_create_default and sheet_name == "기본":
            max_order = db.query(func.max(TestCaseSheet.sort_order)).filter(
                TestCaseSheet.project_id == project_id
            ).scalar() or 0
            new_sheet = TestCaseSheet(
                project_id=project_id, name="기본", sort_order=max_order + 1,
            )
            db.add(new_sheet)
            db.flush()
            return
        raise HTTPException(status_code=400, detail=f"존재하지 않는 시트입니다: {sheet_name}")
    if sheet.is_folder:
        raise HTTPException(status_code=400, detail="폴더에는 TC를 직접 추가할 수 없습니다. 하위 시트를 사용하세요.")
