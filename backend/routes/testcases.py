import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import User, Project, TestCase, TestCaseHistory
from schemas import (
    TestCaseCreate, TestCaseUpdate, TestCaseResponse, TestCaseBulkUpdate,
)
from auth import get_current_user, role_required, check_project_access
from routes.sheets import _validate_sheet_name
from services.tc_id_service import allocate_tc_id, taken_tc_ids
from services.import_service import (
    HEADER_MAP, SKIP_SHEETS, _resolve_merged, _detect_header_row, _count_tc_rows,
    _parse_sheet, _parse_csv, _load_workbook_from_upload, _is_csv_file,
    _is_md_file, _decode_text, _preview_md, _parse_md_tables,
    _parse_md_table, _preview_csv, MAX_IMPORT_SIZE,
)
from services.export_service import export_testcases_excel
from services.run_sync_service import sync_project_in_progress_runs

logger = logging.getLogger(__name__)


def _record_history(db: Session, tc: TestCase, changes: dict, user_id: int):
    """Record field-level change history for a test case."""
    for field, (old_val, new_val) in changes.items():
        db.add(TestCaseHistory(
            test_case_id=tc.id,
            changed_by=user_id,
            field_name=field,
            old_value=str(old_val) if old_val is not None else None,
            new_value=str(new_val) if new_val is not None else None,
        ))

router = APIRouter(
    prefix="/api/projects/{project_id}/testcases",
    tags=["testcases"],
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── List ──────────────────────────────────────────────────────────────────────

MAX_LIST_LIMIT = 5000  # 단일 요청 최대 반환 건수


@router.get("", response_model=List[TestCaseResponse])
def list_testcases(
    project_id: int,
    category: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    sheet_name: Optional[str] = Query(None),
    limit: Optional[int] = Query(None, ge=1, le=MAX_LIST_LIMIT),
    offset: Optional[int] = Query(None, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    _get_project_or_404(project_id, db)

    q = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))

    if sheet_name:
        q = q.filter(TestCase.sheet_name == sheet_name)
    if category:
        q = q.filter(TestCase.category == category)
    if priority:
        q = q.filter(TestCase.priority == priority)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (TestCase.tc_id.ilike(like))
            | (TestCase.depth1.ilike(like))
            | (TestCase.depth2.ilike(like))
            | (TestCase.test_steps.ilike(like))
            | (TestCase.expected_result.ilike(like))
        )

    q = q.order_by(TestCase.no)
    if offset is not None:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    else:
        q = q.limit(MAX_LIST_LIMIT)

    return q.all()


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=TestCaseResponse, status_code=status.HTTP_201_CREATED)
def create_testcase(
    project_id: int,
    payload: TestCaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)
    _validate_sheet_name(project_id, payload.sheet_name, db, auto_create_default=True)

    tc = TestCase(
        project_id=project_id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(tc)
    db.commit()
    sync_project_in_progress_runs(project_id, db)
    db.refresh(tc)
    return tc


# ── Bulk Update ───────────────────────────────────────────────────────────────
# NOTE: /bulk must be defined BEFORE /{tc_id} so FastAPI doesn't try to parse
# "bulk" as an integer tc_id.

@router.put("/bulk", response_model=List[TestCaseResponse])
def bulk_update_testcases(
    project_id: int,
    payload: TestCaseBulkUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    updated: list[TestCase] = []
    for item in payload.items:
        tc = db.query(TestCase).filter(
            TestCase.id == item.id, TestCase.project_id == project_id
        ).first()
        if not tc:
            continue
        item_data = item.model_dump(exclude_unset=True, exclude={"id"})
        if "sheet_name" in item_data:
            _validate_sheet_name(project_id, item_data["sheet_name"], db)
        changes = {}
        for key, value in item_data.items():
            old_val = getattr(tc, key)
            if str(old_val) != str(value):
                changes[key] = (old_val, value)
            setattr(tc, key, value)
        if changes:
            _record_history(db, tc, changes, current_user.id)
        updated.append(tc)

    db.commit()
    for tc in updated:
        db.refresh(tc)
    return updated


# ── Reorder (drag & drop) ─────────────────────────────────────────────────
# NOTE: /reorder must be defined BEFORE /{tc_id} so FastAPI doesn't try to parse
# "reorder" as an integer tc_id.

class ReorderItem(BaseModel):
    id: int
    no: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


@router.put("/reorder")
def reorder_testcases(
    project_id: int,
    payload: ReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """TC 순서(no)를 일괄 변경한다."""
    _get_project_or_404(project_id, db)

    count = 0
    for item in payload.items:
        updated = (
            db.query(TestCase)
            .filter(TestCase.id == item.id, TestCase.project_id == project_id)
            .update({TestCase.no: item.no}, synchronize_session="fetch")
        )
        count += updated

    db.commit()
    return {"updated": count}


# ── Update ────────────────────────────────────────────────────────────────────

@router.put("/{tc_id}", response_model=TestCaseResponse)
def update_testcase(
    project_id: int,
    tc_id: int,
    payload: TestCaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    tc = db.query(TestCase).filter(
        TestCase.id == tc_id, TestCase.project_id == project_id
    ).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    update_data = payload.model_dump(exclude_unset=True)
    if "sheet_name" in update_data:
        _validate_sheet_name(project_id, update_data["sheet_name"], db)

    changes = {}
    for key, value in update_data.items():
        old_val = getattr(tc, key)
        if str(old_val) != str(value):
            changes[key] = (old_val, value)
        setattr(tc, key, value)

    if changes:
        _record_history(db, tc, changes, current_user.id)

    db.commit()
    db.refresh(tc)
    return tc


# ── Delete (soft) ────────────────────────────────────────────────────────────

@router.delete("/bulk")
def bulk_delete_testcases(
    project_id: int,
    ids: str = Query(..., description="쉼표 구분 TC ID 목록"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """여러 TC를 한 번에 소프트 삭제한다."""
    _get_project_or_404(project_id, db)
    from models import now_kst
    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    now = now_kst()
    count = (
        db.query(TestCase)
        .filter(TestCase.id.in_(id_list), TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
        .update({TestCase.deleted_at: now}, synchronize_session="fetch")
    )
    db.commit()
    return {"deleted": count}


@router.delete("/{tc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_testcase(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    tc = db.query(TestCase).filter(
        TestCase.id == tc_id, TestCase.project_id == project_id
    ).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found")

    from models import now_kst
    tc.deleted_at = now_kst()
    db.commit()


# ── Restore ──────────────────────────────────────────────────────────────────

@router.post("/{tc_id}/restore", response_model=TestCaseResponse)
def restore_testcase(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    tc = db.query(TestCase).filter(
        TestCase.id == tc_id, TestCase.project_id == project_id,
        TestCase.deleted_at.isnot(None),
    ).first()
    if not tc:
        raise HTTPException(status_code=404, detail="Test case not found or not deleted")

    # 지운 뒤에 같은 TC ID 가 새로 생겼을 수 있다. 그러면 빈 번호로 되살린다.
    # deleted_at 을 풀기 전에 조회한다. 풀고 나서 조회하면 autoflush 가
    # 이 행까지 살아 있는 것으로 반영해 자기 자신과 충돌한다고 판정한다.
    taken = taken_tc_ids(project_id, db)
    tc.deleted_at = None
    if tc.tc_id in taken:
        tc.tc_id = allocate_tc_id(tc.tc_id, taken)
    db.commit()
    sync_project_in_progress_runs(project_id, db)
    db.refresh(tc)
    return tc


# ── Clone ───────────────────────────────────────────────────────────────────

class BulkCloneRequest(BaseModel):
    ids: List[int]


_CLONE_FIELDS = [
    "type", "category", "depth1", "depth2", "priority", "test_type",
    "precondition", "test_steps", "expected_result", "r1", "r2", "r3",
    "remarks", "sheet_name", "custom_fields",
]


def _max_no_in_sheet(project_id: int, sheet_name: str, db: Session) -> int:
    """그 시트에서 쓰인 적 있는 가장 큰 번호.

    ★`no` 는 시트 안 순번이다. 신규 행 추가와 엑셀 임포트는 그렇게 붙이는데
      복제만 프로젝트 전체 max(no)+1 을 줬다. 다른 시트의 큰 번호가 따라와
      시트 안 번호에 구멍이 났고, 그 시트로 만든 수행의 No 가 1 부터 시작하지
      않았다.
    ★지운 TC 도 센다. 삭제는 soft delete 라 되돌릴 수 있어서, 살아 있는 것만
      보면 지운 번호를 복제가 다시 쓰고 복원하는 순간 같은 시트에 같은 번호가
      둘이 된다(실측 재현). 번호에 구멍이 남는 쪽이 낫다. 수행 화면과 내보내기의
      No 는 어차피 목록 순번이라 구멍이 보이지 않는다.
    """
    return db.query(func.max(TestCase.no)).filter(
        TestCase.project_id == project_id,
        TestCase.sheet_name == sheet_name,
    ).scalar() or 0


@router.post("/bulk-clone", response_model=List[TestCaseResponse], status_code=201)
def bulk_clone_testcases(
    project_id: int,
    body: BulkCloneRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    originals = (
        db.query(TestCase)
        .filter(
            TestCase.id.in_(body.ids),
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
        )
        .order_by(TestCase.no)
        .all()
    )
    if not originals:
        raise HTTPException(status_code=404, detail="No test cases found")

    # 여러 시트를 한 번에 복제할 수 있다. 번호는 각자의 시트에서 이어 붙인다.
    next_no: dict[str, int] = {}

    def alloc_no(sheet_name: str) -> int:
        if sheet_name not in next_no:
            next_no[sheet_name] = _max_no_in_sheet(project_id, sheet_name, db)
        next_no[sheet_name] += 1
        return next_no[sheet_name]

    # "-copy" 를 그대로 쓰면 같은 TC 를 두 번 복제할 때 ID 가 겹친다.
    taken = taken_tc_ids(project_id, db)

    cloned = []
    for orig in originals:
        data = {f: getattr(orig, f) for f in _CLONE_FIELDS}
        new_id = allocate_tc_id(f"{orig.tc_id}-copy", taken)
        taken.add(new_id)
        new_tc = TestCase(
            project_id=project_id,
            no=alloc_no(orig.sheet_name),
            tc_id=new_id,
            created_by=current_user.id,
            **data,
        )
        db.add(new_tc)
        cloned.append(new_tc)

    db.commit()
    sync_project_in_progress_runs(project_id, db)
    for tc in cloned:
        db.refresh(tc)
    return cloned


@router.post("/{tc_id}/clone", response_model=TestCaseResponse, status_code=201)
def clone_testcase(
    project_id: int,
    tc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    original = db.query(TestCase).filter(
        TestCase.id == tc_id,
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).first()
    if not original:
        raise HTTPException(status_code=404, detail="Test case not found")

    data = {f: getattr(original, f) for f in _CLONE_FIELDS}
    new_id = allocate_tc_id(f"{original.tc_id}-copy", taken_tc_ids(project_id, db))
    new_tc = TestCase(
        project_id=project_id,
        no=_max_no_in_sheet(project_id, original.sheet_name, db) + 1,
        tc_id=new_id,
        created_by=current_user.id,
        **data,
    )
    db.add(new_tc)
    db.commit()
    sync_project_in_progress_runs(project_id, db)
    db.refresh(new_tc)
    return new_tc


# ── Import ───────────────────────────────────────────────────────────────────

@router.post("/import/preview")
def preview_import_sheets(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    """엑셀/CSV/Markdown 파일의 시트 목록과 각 시트의 TC 수, 기존 중복 수를 반환한다."""
    if _is_csv_file(file.filename):
        content = file.file.read()
        if len(content) > MAX_IMPORT_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_IMPORT_SIZE // (1024*1024)}MB")
        return {"sheets": _preview_csv(content, project_id, db)}

    if _is_md_file(file.filename):
        content = file.file.read()
        if len(content) > MAX_IMPORT_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_IMPORT_SIZE // (1024*1024)}MB")
        return {"sheets": _preview_md(content, project_id, db)}

    wb = _load_workbook_from_upload(file)

    sheets = []
    for name in wb.sheetnames:
        ws = wb[name]
        header_row = _detect_header_row(ws)
        if header_row is None:
            continue
        tc_count = _count_tc_rows(ws, header_row)
        if tc_count == 0:
            continue
        # 기존 동일 시트의 TC 수
        existing = db.query(TestCase).filter(
            TestCase.project_id == project_id,
            TestCase.sheet_name == name,
            TestCase.deleted_at.is_(None),
        ).count()
        sheets.append({"name": name, "tc_count": tc_count, "existing": existing})

    return {"sheets": sheets}


@router.post("/import", status_code=status.HTTP_201_CREATED)
def import_testcases(
    project_id: int,
    file: UploadFile = File(...),
    sheet_names: Optional[str] = Query(None, description="쉼표 구분 시트명 (미지정 시 전체)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    # CSV 파일 처리
    if _is_csv_file(file.filename):
        content = file.file.read()
        if len(content) > MAX_IMPORT_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_IMPORT_SIZE // (1024*1024)}MB")
        sheet_name = "CSV Import"
        from models import TestCaseSheet
        sheet_exists = db.query(TestCaseSheet).filter(
            TestCaseSheet.project_id == project_id, TestCaseSheet.name == sheet_name
        ).first()
        if not sheet_exists:
            max_order = db.query(TestCaseSheet.sort_order).filter(
                TestCaseSheet.project_id == project_id
            ).order_by(TestCaseSheet.sort_order.desc()).first()
            db.add(TestCaseSheet(project_id=project_id, name=sheet_name, sort_order=(max_order[0] + 1) if max_order else 0))
            db.flush()
        r = _parse_csv(content, project_id, current_user.id, db, sheet_name=sheet_name)
        db.commit()
        sync_project_in_progress_runs(project_id, db)
        return {"created": r["created"], "updated": r["updated"], "renamed": r.get("renamed", 0), "imported": r["created"] + r["updated"], "sheets": [{"sheet": sheet_name, "created": r["created"], "updated": r["updated"], "renamed": r.get("renamed", 0)}]}

    # Markdown 파일 처리
    if _is_md_file(file.filename):
        content = file.file.read()
        if len(content) > MAX_IMPORT_SIZE:
            raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_IMPORT_SIZE // (1024*1024)}MB")
        tables = _parse_md_tables(content)
        if not tables:
            return {"created": 0, "updated": 0, "renamed": 0, "imported": 0, "sheets": []}

        if sheet_names:
            target_names = [s.strip() for s in sheet_names.split(",") if s.strip()]
        else:
            target_names = [t["name"] for t in tables]

        from models import TestCaseSheet
        total_created = 0
        total_updated = 0
        total_renamed = 0
        results = []
        for table in tables:
            if table["name"] not in target_names:
                continue
            # 시트 레코드 자동 생성
            sheet_exists = db.query(TestCaseSheet).filter(
                TestCaseSheet.project_id == project_id, TestCaseSheet.name == table["name"]
            ).first()
            if not sheet_exists:
                max_order = db.query(TestCaseSheet.sort_order).filter(
                    TestCaseSheet.project_id == project_id
                ).order_by(TestCaseSheet.sort_order.desc()).first()
                db.add(TestCaseSheet(project_id=project_id, name=table["name"], sort_order=(max_order[0] + 1) if max_order else 0))
                db.flush()
            r = _parse_md_table(table, project_id, current_user.id, db, sheet_name=table["name"])
            results.append({"sheet": table["name"], "created": r["created"], "updated": r["updated"], "renamed": r.get("renamed", 0)})
            total_created += r["created"]
            total_updated += r["updated"]
            total_renamed += r.get("renamed", 0)

        db.commit()
        sync_project_in_progress_runs(project_id, db)
        return {"created": total_created, "updated": total_updated, "renamed": total_renamed, "imported": total_created + total_updated, "sheets": results}

    wb = _load_workbook_from_upload(file)

    # 대상 시트 결정
    if sheet_names:
        target_names = [s.strip() for s in sheet_names.split(",") if s.strip()]
    else:
        # 미지정 시: 유효한 시트 전부 (SKIP_SHEETS 제외)
        target_names = []
        for name in wb.sheetnames:
            if name.upper() in SKIP_SHEETS:
                continue
            ws = wb[name]
            if _detect_header_row(ws) is not None:
                target_names.append(name)
        # 아무것도 없으면 첫 시트
        if not target_names and wb.sheetnames:
            target_names = [wb.sheetnames[0]]

    total_created = 0
    total_updated = 0
    total_renamed = 0
    results = []
    for name in target_names:
        if name not in wb.sheetnames:
            continue
        ws = wb[name]
        # 시트 레코드 자동 생성
        from models import TestCaseSheet
        sheet_exists = db.query(TestCaseSheet).filter(
            TestCaseSheet.project_id == project_id, TestCaseSheet.name == name
        ).first()
        if not sheet_exists:
            max_order = db.query(TestCaseSheet.sort_order).filter(
                TestCaseSheet.project_id == project_id
            ).order_by(TestCaseSheet.sort_order.desc()).first()
            db.add(TestCaseSheet(project_id=project_id, name=name, sort_order=(max_order[0] + 1) if max_order else 0))
            db.flush()

        r = _parse_sheet(ws, project_id, current_user.id, db, no_offset=0, sheet_name=name)
        results.append({"sheet": name, "created": r["created"], "updated": r["updated"], "renamed": r.get("renamed", 0)})
        total_created += r["created"]
        total_updated += r["updated"]
        total_renamed += r.get("renamed", 0)

    db.commit()
    sync_project_in_progress_runs(project_id, db)
    return {"created": total_created, "updated": total_updated, "renamed": total_renamed, "imported": total_created + total_updated, "sheets": results}


# ── Export ───────────────────────────────────────────────────────────────────

@router.get("/export")
def export_testcases(
    project_id: int,
    split_sheets: bool = False,
    expand_refs: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    project = _get_project_or_404(project_id, db)
    testcases = (
        db.query(TestCase)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
        .order_by(TestCase.no)
        .all()
    )
    return export_testcases_excel(project, testcases, split_sheets, expand_refs)
