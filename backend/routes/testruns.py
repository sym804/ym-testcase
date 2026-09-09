import io
import os
from datetime import datetime
from models import now_kst
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, subqueryload, load_only
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

from database import get_db
from models import User, Project, TestCase, TestCaseSheet, TestRun, TestResult, TestRunStatus, TestResultValue, Attachment
from schemas import (
    TestRunCreate, TestRunUpdate, TestRunResponse, TestRunListResponse,
    TestResultCreate, TestResultResponse,
)
from auth import get_current_user, role_required, check_project_access, get_project_role
from routes.attachments import UPLOAD_DIR
from services.run_sync_service import sync_run_results
from services.excel_safe import safe_cell
from services.sheet_order import leaf_sheet_order, sort_results_for_export

router = APIRouter(
    prefix="/api/projects/{project_id}/testruns",
    tags=["testruns"],
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("", response_model=List[TestRunListResponse])
def list_testruns(
    project_id: int,
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    _get_project_or_404(project_id, db)
    return (
        db.query(TestRun)
        .filter(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.post("", response_model=TestRunListResponse, status_code=status.HTTP_201_CREATED)
def create_testrun(
    project_id: int,
    payload: TestRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    _get_project_or_404(project_id, db)

    # test_plan_id가 지정된 경우 같은 프로젝트의 플랜인지 검증
    if payload.test_plan_id is not None:
        from models import TestPlan
        plan = db.query(TestPlan).filter(TestPlan.id == payload.test_plan_id).first()
        if not plan:
            raise HTTPException(status_code=400, detail="존재하지 않는 테스트 플랜입니다.")
        if plan.project_id != project_id:
            raise HTTPException(status_code=400, detail="다른 프로젝트의 테스트 플랜은 연결할 수 없습니다.")

    # 시트를 골라 만든 런은 그 범위를 저장한다. 생성 시점의 필터가 아니라 런의
    # 범위라서, 진행 중 런이 새 TC 를 흡수할 때도 같은 조건을 쓴다.
    sheet_names = None
    if payload.sheet_names is not None:
        # 같은 이름을 여러 번 보내도 한 번만 저장한다. 순서는 보낸 순서를 지킨다.
        sheet_names = list(dict.fromkeys(n.strip() for n in payload.sheet_names if n and n.strip()))
        if not sheet_names:
            raise HTTPException(status_code=400, detail="시트를 하나 이상 선택하세요.")
        # 폴더는 TC 를 직접 담지 않는다. 범위로 받으면 빈 런이 되므로 거부한다.
        known = {
            row[0] for row in db.query(TestCaseSheet.name)
            .filter(
                TestCaseSheet.project_id == project_id,
                TestCaseSheet.is_folder.is_(False),
            ).all()
        }
        unknown = [n for n in sheet_names if n not in known]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"런에 담을 수 없는 시트입니다: {', '.join(unknown)}",
            )

    run = TestRun(
        project_id=project_id,
        name=payload.name,
        version=payload.version,
        environment=payload.environment,
        round=payload.round,
        test_plan_id=payload.test_plan_id,
        sheet_names=sheet_names,
        created_by=current_user.id,
    )
    db.add(run)
    db.flush()  # get run.id

    # Auto-create empty TestResult for each TC in the project (bulk insert)
    tc_q = (
        db.query(TestCase.id)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
    )
    if sheet_names is not None:
        tc_q = tc_q.filter(TestCase.sheet_name.in_(sheet_names))
    tc_ids = [row[0] for row in tc_q.order_by(TestCase.no).all()]
    if tc_ids:
        db.bulk_insert_mappings(TestResult, [
            {
                "test_run_id": run.id,
                "test_case_id": tc_id,
                "result": TestResultValue.NS,
                "executed_by": current_user.id,
            }
            for tc_id in tc_ids
        ])

    db.commit()
    db.refresh(run)
    return run


@router.get("/{run_id}", response_model=TestRunResponse)
def get_testrun(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    _get_project_or_404(project_id, db)

    run = (
        db.query(TestRun)
        .filter(TestRun.id == run_id, TestRun.project_id == project_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    # 런 생성 이후 추가된 TC 반영 (진행 중인 런만).
    # TC 생성 경로에서 이미 반영되므로 여기는 이 수정 이전에 만들어진 런을 위한 안전망이다.
    # viewer는 읽기 전용 역할이므로 조회만으로 쓰기가 일어나지 않도록 tester 이상에서만 보정한다
    # (공개 프로젝트는 비멤버도 viewer로 취급되기 때문에 특히 중요하다).
    if get_project_role(project_id, current_user, db) in ("tester", "admin"):
        sync_run_results(run, db)

    loaded = (
        db.query(TestRun)
        .options(
            subqueryload(TestRun.results)
            .joinedload(TestResult.test_case)
        )
        .filter(TestRun.id == run_id, TestRun.project_id == project_id)
        .first()
    )

    # 결과 행은 런에 편입된 순서로 저장되므로, 나중에 추가된 TC는 뒤에 붙는다.
    # 소비자는 저마다 다시 세운다(그리드는 시트 순서 + no, 두 엑셀은 leaf_sheet_order).
    # 그래도 여기서 no 순을 보장한다. 시트를 모르는 소비자(API 를 직접 부르는 쪽)가
    # 편입 순서를 그대로 받으면 순서가 없는 것이나 마찬가지다.
    # 세션에서 분리한 뒤 정렬해 ORM 컬렉션 변경으로 잡히지 않게 한다.
    if loaded:
        db.expunge(loaded)
        loaded.results.sort(key=lambda r: r.test_case.no if r.test_case else 0)
    return loaded


@router.put("/{run_id}", response_model=TestRunListResponse)
def update_testrun(
    project_id: int,
    run_id: int,
    payload: TestRunUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    _get_project_or_404(project_id, db)

    run = db.query(TestRun).filter(
        TestRun.id == run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    for key, value in payload.model_dump(exclude_unset=True).items():
        # 라운드를 비우면 커밋에서 제약에 걸려 409 가 난다. 무엇이 잘못됐는지
        # 알 수 없는 메시지라, 여기서 이유를 붙여 거절한다.
        if key == "round" and value is None:
            raise HTTPException(status_code=400, detail="라운드는 비울 수 없습니다.")
        setattr(run, key, value)

    db.commit()
    db.refresh(run)
    return run


@router.post("/{run_id}/results", response_model=List[TestResultResponse])
def submit_results(
    project_id: int,
    run_id: int,
    results: List[TestResultCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    _get_project_or_404(project_id, db)

    run = db.query(TestRun).filter(
        TestRun.id == run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    if run.status == TestRunStatus.completed:
        raise HTTPException(status_code=400, detail="완료된 테스트 런은 수정할 수 없습니다. 재오픈 후 수정하세요.")

    # Validate all test_case_ids belong to this project
    tc_ids = [r.test_case_id for r in results]
    valid_tc_ids = set(
        row[0] for row in db.query(TestCase.id).filter(
            TestCase.project_id == project_id, TestCase.id.in_(tc_ids)
        ).all()
    )
    invalid_ids = set(tc_ids) - valid_tc_ids
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail="One or more test case IDs are invalid for this project",
        )

    # ★프로젝트 소속만 보면 시트를 골라 만든 런에 범위 밖 TC 가 들어온다.
    #   결과 행이 없으면 아래에서 새로 만들기 때문에, 여기서 막지 않으면 제출 한 번으로
    #   런의 범위가 늘어난다.
    if run.sheet_names is not None:
        outside = [
            row[0] for row in db.query(TestCase.tc_id).filter(
                TestCase.id.in_(tc_ids),
                ~TestCase.sheet_name.in_(run.sheet_names),
            ).all()
        ]
        if outside:
            raise HTTPException(
                status_code=400,
                detail=f"이 수행의 시트 범위 밖 TC 입니다: {', '.join(outside[:5])}",
            )

    # Validate all result enums upfront
    for r in results:
        try:
            TestResultValue(r.result)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid result value: {r.result}. Must be one of PASS, FAIL, BLOCK, NA, NS",
            )

    # Prefetch existing results in a single query (N+1 방지)
    existing_map: dict[int, TestResult] = {}
    existing_results = db.query(TestResult).filter(
        TestResult.test_run_id == run_id,
        TestResult.test_case_id.in_(tc_ids),
    ).all()
    for er in existing_results:
        existing_map[er.test_case_id] = er

    saved: list[TestResult] = []
    for r in results:
        result_enum = TestResultValue(r.result)

        # Parse optional time fields
        started = None
        finished = None
        if r.started_at:
            try:
                started = datetime.fromisoformat(r.started_at)
            except (ValueError, TypeError):
                pass
        if r.finished_at:
            try:
                finished = datetime.fromisoformat(r.finished_at)
            except (ValueError, TypeError):
                pass

        existing = existing_map.get(r.test_case_id)
        if existing:
            existing.result = result_enum
            existing.actual_result = r.actual_result
            existing.issue_link = r.issue_link
            existing.remarks = r.remarks
            existing.executed_by = current_user.id
            existing.executed_at = now_kst()
            if started:
                existing.started_at = started
            if finished:
                existing.finished_at = finished
            if r.duration_sec is not None:
                existing.duration_sec = r.duration_sec
            saved.append(existing)
        else:
            tr = TestResult(
                test_run_id=run_id,
                test_case_id=r.test_case_id,
                result=result_enum,
                actual_result=r.actual_result,
                issue_link=r.issue_link,
                remarks=r.remarks,
                executed_by=current_user.id,
            )
            db.add(tr)
            saved.append(tr)

    try:
        db.commit()
    except IntegrityError as exc:
        # ★같은 TC 를 동시에 제출하면 둘 다 "없음" 으로 보고 각자 새 행을 넣는다.
        #   유니크 제약이 뒤늦게 잡아 주므로 그대로 500 을 내지 말고 다시 시도하게 한다.
        # ★유니크 위반만 409 로 바꾼다. 외래키 위반 같은 다른 무결성 오류까지 삼키면
        #   원인이 다른 사고를 "동시 저장" 으로 오인시켜 헛된 재시도를 유도한다(QA1 지적).
        db.rollback()
        if "uq_test_results_run_case" not in str(getattr(exc, "orig", exc)):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="같은 테스트 케이스의 결과가 동시에 저장됐습니다. 새로고침 후 다시 시도해주세요.",
        )
    for item in saved:
        db.refresh(item)
    return saved


@router.put("/{run_id}/complete", response_model=TestRunListResponse)
def complete_testrun(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    _get_project_or_404(project_id, db)

    run = db.query(TestRun).filter(
        TestRun.id == run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    run.status = TestRunStatus.completed
    run.completed_at = now_kst()

    db.commit()
    db.refresh(run)
    return run


@router.put("/{run_id}/reopen", response_model=TestRunListResponse)
def reopen_testrun(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    """완료된 테스트 런을 다시 진행 중으로 변경한다."""
    _get_project_or_404(project_id, db)

    run = db.query(TestRun).filter(
        TestRun.id == run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    run.status = TestRunStatus.in_progress
    run.completed_at = None
    db.commit()

    # 완료 상태였던 동안 추가된 TC는 동기화 대상에서 빠져 있었다.
    # 다시 진행 중이 된 시점에 흡수해야, 상세를 열지 않고 바로 완료해도 누락되지 않는다.
    sync_run_results(run, db)

    db.refresh(run)
    return run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_testrun(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    run = db.query(TestRun).filter(
        TestRun.id == run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    result_ids = [r.id for r in db.query(TestResult.id).filter(TestResult.test_run_id == run_id).all()]
    if result_ids:
        attachments = db.query(Attachment).filter(Attachment.test_result_id.in_(result_ids)).all()
        for att in attachments:
            if att.filepath:
                full_path = os.path.join(UPLOAD_DIR, att.filepath)
                if os.path.isfile(full_path):
                    try:
                        os.remove(full_path)
                    except OSError:
                        pass
        # bulk delete로 처리 (개별 db.delete()는 cascade와 충돌하여 경고 발생)
        db.query(Attachment).filter(Attachment.test_result_id.in_(result_ids)).delete(synchronize_session=False)
    db.query(TestResult).filter(TestResult.test_run_id == run_id).delete(synchronize_session=False)
    db.delete(run)
    db.commit()


@router.post("/{run_id}/clone", response_model=TestRunListResponse, status_code=status.HTTP_201_CREATED)
def clone_testrun(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    """Clone an existing test run with all its test results reset to NS."""
    _get_project_or_404(project_id, db)

    source = (
        db.query(TestRun)
        .options(joinedload(TestRun.results))
        .filter(TestRun.id == run_id, TestRun.project_id == project_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Test run not found")

    new_run = TestRun(
        project_id=project_id,
        name=f"{source.name} (복제)",
        version=source.version,
        environment=source.environment,
        round=source.round,
        sheet_names=source.sheet_names,
        created_by=current_user.id,
    )
    db.add(new_run)
    db.flush()

    if source.results:
        # ★원본 런에 같은 TC 결과가 둘 이상이면 그대로 복사돼 새 런에도 중복이 생긴다.
        #   유니크 제약이 생긴 뒤로는 아예 실패한다. TC 기준으로 한 번만 넣는다.
        seen = set()
        rows = []
        for r in source.results:
            if r.test_case_id in seen:
                continue
            seen.add(r.test_case_id)
            rows.append({
                "test_run_id": new_run.id,
                "test_case_id": r.test_case_id,
                "result": TestResultValue.NS,
                "executed_by": current_user.id,
            })
        db.bulk_insert_mappings(TestResult, rows)

    db.commit()
    db.refresh(new_run)
    return new_run


@router.get("/{run_id}/export")
def export_testrun_excel(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """Export test run results as Excel file."""
    _get_project_or_404(project_id, db)

    run = (
        db.query(TestRun)
        .options(
            subqueryload(TestRun.results)
            .joinedload(TestResult.test_case)
            .load_only(
                TestCase.id, TestCase.no, TestCase.tc_id, TestCase.type,
                TestCase.category, TestCase.depth1, TestCase.depth2,
                TestCase.priority, TestCase.test_steps, TestCase.expected_result,
                # 시트 순서로 세우려면 필요하다. 빼면 행마다 지연 로딩이 붙는다.
                TestCase.sheet_name,
            )
        )
        .filter(TestRun.id == run_id, TestRun.project_id == project_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")

    wb = Workbook()
    ws = wb.active
    ws.title = "Test Results"

    # Header style
    header_font = Font(bold=True, color="FFFFFF", size=10)
    header_fill = PatternFill(start_color="1A2744", end_color="1A2744", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    headers = ["No", "TC ID", "Type", "Category", "Depth1", "Depth2", "Priority",
               "Test Steps", "Expected Result", "Result", "Actual Result",
               "Issue Link", "Duration(sec)", "Remarks"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Result color fills
    result_fills = {
        "PASS": PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid"),
        "FAIL": PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid"),
        "BLOCK": PatternFill(start_color="FEF9C3", end_color="FEF9C3", fill_type="solid"),
        "NA": PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid"),
    }

    # ★화면과 같은 차례로 세운다. 시트 순서가 먼저고 그 안에서 no 순이다.
    #   no 로만 세우면 여러 시트를 담은 수행에서 시트가 뒤섞인다.
    sorted_results = sort_results_for_export(run.results, leaf_sheet_order(project_id, db))

    for row_idx, tr in enumerate(sorted_results, 2):
        tc = tr.test_case
        result_display = "" if tr.result == TestResultValue.NS else ("N/A" if tr.result == TestResultValue.NA else tr.result.value)

        # ★No 는 저장된 no 가 아니라 이 목록의 순번이다. 파일은 수행 전체를 담으므로
        #   화면의 "전체" 탭과 같은 번호가 된다(시트 탭은 그 시트 안에서 다시 1 부터다).
        #   저장된 no 는 시트 안에서 구멍이 날 수 있어 화면과 파일이 갈렸다.
        ws.cell(row=row_idx, column=1, value=row_idx - 1)
        # 사용자가 쓴 값은 그대로 넣지 않는다. =, +, -, @ 로 시작하면 여는 쪽에서
        # 수식으로 실행된다(CWE-1236). TC 목록 내보내기에만 있던 방어를 여기도 건다.
        ws.cell(row=row_idx, column=2, value=safe_cell(tc.tc_id if tc else ""))
        ws.cell(row=row_idx, column=3, value=safe_cell(tc.type if tc else ""))
        ws.cell(row=row_idx, column=4, value=safe_cell(tc.category if tc else ""))
        ws.cell(row=row_idx, column=5, value=safe_cell(tc.depth1 if tc else ""))
        ws.cell(row=row_idx, column=6, value=safe_cell(tc.depth2 if tc else ""))
        ws.cell(row=row_idx, column=7, value=safe_cell(tc.priority if tc else ""))
        ws.cell(row=row_idx, column=8, value=safe_cell(tc.test_steps if tc else "")).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_idx, column=9, value=safe_cell(tc.expected_result if tc else "")).alignment = Alignment(wrap_text=True)
        result_cell = ws.cell(row=row_idx, column=10, value=result_display)
        result_cell.alignment = Alignment(horizontal="center")
        if tr.result.value in result_fills:
            result_cell.fill = result_fills[tr.result.value]
        ws.cell(row=row_idx, column=11, value=safe_cell(tr.actual_result or "")).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_idx, column=12, value=safe_cell(tr.issue_link or ""))
        ws.cell(row=row_idx, column=13, value=tr.duration_sec or "")
        ws.cell(row=row_idx, column=14, value=safe_cell(tr.remarks or "")).alignment = Alignment(wrap_text=True)

    # Auto-width (approximate)
    col_widths = [6, 12, 8, 14, 14, 14, 10, 40, 30, 10, 30, 20, 10, 20]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    # ★헤더는 latin-1 만 담는다. 수행 이름에 한글이 있으면 그대로 넣다가 인코딩에서
    #   터져 500 이 났다(실측: 같은 수행을 영문 이름으로 만들면 200).
    #   다른 내보내기(리포트, TC 목록)가 쓰는 RFC 5987 방식으로 맞춘다.
    from urllib.parse import quote
    filename = f"{run.name}_results.xlsx"
    encoded = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
