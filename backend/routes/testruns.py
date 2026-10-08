import io
import os
from datetime import datetime
from models import now_kst
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, subqueryload, load_only
from sqlalchemy import func, case
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
from services.locks import LockNs, advisory_xact_lock, project_write_lock
from services.run_sync_service import sync_run_results
from services.excel_safe import safe_cell
from services.sheet_order import leaf_sheet_order, sort_results_for_export
from services.upload_guard import read_limited_sync
from services.result_import import (
    ImportFormatError, parse_report, aggregate,
    KIND_FIXED, KIND_FAIL, KIND_KNOWN_FAIL,
)

#: 자동화 결과 파일 상한. 전량 스위트(230여 건) JSON 이 수 MB 라 여유를 둔다.
MAX_RESULT_IMPORT_SIZE = 20 * 1024 * 1024
FORMAT_LABEL = {"playwright-json": "Playwright JSON", "junit-xml": "JUnit XML"}
#: 응답에 싣는 미매칭 제목 상한. 나머지는 건수만 준다.
MAX_UNMATCHED_LISTED = 200

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
    runs = (
        db.query(TestRun)
        .filter(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    # 목록 항목에 진행률을 싣는다(런 수와 무관하게 SQL 1회). 상세를 열지 않아도 어느
    # 회차가 얼마나 진행됐는지 트리에서 보이게 한다(09-30, 수행이 많아질 때의 관리).
    progress = _bulk_run_progress([r.id for r in runs], db)
    out = []
    for r in runs:
        item = TestRunListResponse.model_validate(r)
        item.tc_total, item.tc_executed = progress.get(r.id, (0, 0))
        out.append(item)
    return out


def _bulk_run_progress(run_ids: list[int], db: Session) -> dict[int, tuple[int, int]]:
    """런별 (담은 TC 수, 수행한 수). 수행한 수는 NS 가 아닌 결과 행이다."""
    if not run_ids:
        return {}
    rows = (
        db.query(
            TestResult.test_run_id,
            func.count(TestResult.id),
            func.sum(case((TestResult.result != TestResultValue.NS, 1), else_=0)),
        )
        .filter(TestResult.test_run_id.in_(run_ids))
        .group_by(TestResult.test_run_id)
        .all()
    )
    return {run_id: (int(total), int(executed or 0)) for run_id, total, executed in rows}


@router.post("", response_model=TestRunListResponse, status_code=status.HTTP_201_CREATED)
def create_testrun(
    project_id: int,
    payload: TestRunCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
    # TC 생성·동기화와 줄 세운다. 안 그러면 수행이 TC 목록을 읽은 뒤 새 TC 가 커밋되고,
    # 그 TC 의 동기화는 아직 커밋 전인 이 수행을 못 봐 결과 행이 빠진다(QA1 지적).
    _lock: None = Depends(project_write_lock),
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

    sheet_names = _validate_sheet_names(project_id, payload.sheet_names, db)
    run = _new_run(
        project_id, current_user, db,
        name=payload.name,
        version=payload.version,
        environment=payload.environment,
        round_=payload.round,
        test_plan_id=payload.test_plan_id,
        sheet_names=sheet_names,
    )
    db.commit()
    db.refresh(run)
    return run


def _validate_sheet_names(project_id: int, names: Optional[List[str]], db: Session) -> Optional[List[str]]:
    """런 범위로 받을 시트 이름을 고른다. None 이면 프로젝트 전체.

    시트를 골라 만든 런은 그 범위를 저장한다. 생성 시점의 필터가 아니라 런의
    범위라서, 진행 중 런이 새 TC 를 흡수할 때도 같은 조건을 쓴다.
    """
    if names is None:
        return None
    # 같은 이름을 여러 번 보내도 한 번만 저장한다. 순서는 보낸 순서를 지킨다.
    sheet_names = list(dict.fromkeys(n.strip() for n in names if n and n.strip()))
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
    return sheet_names


def _new_run(
    project_id: int, user: User, db: Session, *, name: str, version, environment,
    round_: int, test_plan_id, sheet_names: Optional[List[str]],
) -> TestRun:
    """런을 만들고 범위의 TC 를 NS 로 담는다. 커밋은 부른 쪽이 한다."""
    run = TestRun(
        project_id=project_id,
        name=name,
        version=version,
        environment=environment,
        round=round_,
        test_plan_id=test_plan_id,
        sheet_names=sheet_names,
        created_by=user.id,
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
                "executed_by": user.id,
            }
            for tc_id in tc_ids
        ])
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
        # 비교 대상은 같은 프로젝트의 다른 수행만 받는다. 다른 프로젝트의 수행 id 를
        # 넣으면 리포트에 그 수행의 이름과 결과가 실린다.
        if key == "compare_run_id" and value is not None:
            if value == run.id:
                raise HTTPException(status_code=400, detail="Cannot compare a run with itself")
            exists = db.query(TestRun.id).filter(
                TestRun.id == value, TestRun.project_id == project_id,
            ).first()
            if not exists:
                raise HTTPException(status_code=400, detail="Compare run not found in this project")
        setattr(run, key, value)

    db.commit()
    db.refresh(run)
    return run


def _stale_rows(results, existing_map: dict, db: Session) -> list[str]:
    """expected_executed_at 을 보낸 행 가운데 서버의 executed_at 과 다른 행의 TC ID."""
    stale_ids = []
    for r in results:
        if not r.expected_executed_at:
            continue
        existing = existing_map.get(r.test_case_id)
        if existing is None or existing.executed_at is None:
            continue
        try:
            expected = datetime.fromisoformat(r.expected_executed_at)
        except (ValueError, TypeError):
            continue
        # 마이크로초 단위 저장이라 그대로 비교한다. JSON 왕복에서 tz 는 붙지 않는다(naive KST).
        if existing.executed_at.replace(tzinfo=None) != expected.replace(tzinfo=None):
            stale_ids.append(r.test_case_id)
    if not stale_ids:
        return []
    names = dict(db.query(TestCase.id, TestCase.tc_id).filter(TestCase.id.in_(stale_ids)).all())
    return [names.get(i) or str(i) for i in stale_ids]


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
    # ★결과를 쓰는 세 경로(저장, 파일 가져오기, 누락 행 동기화)가 같은 수행 잠금을 먼저 잡는다.
    #   잡지 않으면 가져오기가 읽고 판단한 사이 사람이 저장한 값을 덮고, 누락 행을 서로 다른
    #   순서로 넣다가 교착한다. 같은 수행의 저장은 짧아서 줄을 서도 체감이 작다.
    advisory_xact_lock(db, LockNs.RUN_RESULTS, run.id)

    tc_ids = [r.test_case_id for r in results]

    # ★이미 이 런에 결과 행이 있는 TC 는 두 검사 모두 통과시킨다.
    #
    #   런은 한 번 담은 행을 빼지 않는다(빼면 기록한 결과가 날아간다). 그래서 TC 를
    #   지우거나 시트를 옮겨도 그 행은 런 상세에 계속 보인다. 그런데 저장만 막으면
    #   사라지지도 채워지지도 않는 행이 남는다. 게다가 결과 제출은 여러 행을 한
    #   배열로 보내므로(범위 채우기, Ctrl+D), 그런 행이 하나 섞이면 배치 전체가
    #   거절되어 같이 입력한 멀쩡한 행까지 날아간다.
    #
    #   두 검사가 막아야 하는 것은 "런에 없던 TC 가 제출로 끼어드는 것" 뿐이다.
    already_in_run = {
        row[0] for row in db.query(TestResult.test_case_id).filter(
            TestResult.test_run_id == run_id,
            TestResult.test_case_id.in_(tc_ids),
        ).all()
    }
    newcomers = [i for i in tc_ids if i not in already_in_run]

    # Validate all test_case_ids belong to this project
    #
    # 지운 TC 를 제출로 새로 끌어들이는 것은 막는다. 그 결과는 어느 집계 기준을
    # 쓰든 어긋나고, 7일 뒤 TC 가 완전히 지워지면 같이 사라진다.
    valid_tc_ids = set(
        row[0] for row in db.query(TestCase.id).filter(
            TestCase.project_id == project_id,
            TestCase.id.in_(newcomers),
            TestCase.deleted_at.is_(None),
        ).all()
    )
    invalid_ids = set(newcomers) - valid_tc_ids
    if invalid_ids:
        raise HTTPException(
            status_code=400,
            detail="이 프로젝트에 없거나 이미 삭제된 TC 입니다.",
        )

    # ★프로젝트 소속만 보면 시트를 골라 만든 런에 범위 밖 TC 가 들어온다.
    #   결과 행이 없으면 아래에서 새로 만들기 때문에, 여기서 막지 않으면 제출 한 번으로
    #   런의 범위가 늘어난다.
    if run.sheet_names is not None:
        outside = [
            row[0] for row in db.query(TestCase.tc_id).filter(
                TestCase.id.in_(newcomers),
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
    # ★행을 잠그고 읽는다. 잠그지 않으면 두 요청이 같은 executed_at 을 보고 둘 다 아래
    #   충돌 검사를 통과해 늦게 끝난 쪽이 덮는다(PostgreSQL 전환 후 6명 동시 저장 6건 성공 재현).
    #   잠금을 기다린 쪽은 앞선 커밋 뒤의 값을 다시 읽어 검사에 걸린다. 교착을 피하려고 id 순서로 잠근다.
    existing_map: dict[int, TestResult] = {}
    existing_results = db.query(TestResult).filter(
        TestResult.test_run_id == run_id,
        TestResult.test_case_id.in_(tc_ids),
    ).order_by(TestResult.id).with_for_update().all()
    for er in existing_results:
        existing_map[er.test_case_id] = er

    # ★낙관적 잠금. 화면이 읽어 둔 executed_at 을 같이 보내면, 그 뒤에 다른 사람이 같은 행을
    #   저장했는지 본다. 자동 저장은 행마다 300ms 뒤 PUT 이고 먼저 나간 요청을 취소하지 못해서,
    #   두 사람이 같은 행을 고치면 늦게 도착한 옛 값이 새 값을 덮었다(09-30, 팀 사용 대비).
    #   하나라도 어긋나면 배치 전체를 거절한다. 일부만 저장하면 화면과 서버가 반쯤 갈린다.
    conflicts = _stale_rows(results, existing_map, db)
    if conflicts:
        raise HTTPException(
            status_code=409,
            detail="다른 사용자가 먼저 저장한 행이 있습니다: " + ", ".join(conflicts)
            + ". 최신 값으로 다시 읽습니다.",
        )

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
            # ★새로 만드는 행에도 타이머 값을 넣는다. 갱신 분기에만 넣어 두면
            #   결과 행이 아직 없는 TC 에 처음 입력할 때 잰 시간이 조용히 버려진다.
            tr = TestResult(
                test_run_id=run_id,
                test_case_id=r.test_case_id,
                result=result_enum,
                actual_result=r.actual_result,
                issue_link=r.issue_link,
                remarks=r.remarks,
                executed_by=current_user.id,
                started_at=started,
                finished_at=finished,
                duration_sec=r.duration_sec,
            )
            db.add(tr)
            saved.append(tr)

    try:
        db.commit()
    except IntegrityError as exc:
        # ★같은 TC 를 동시에 제출하면 둘 다 "없음" 으로 보고 각자 새 행을 넣는다.
        #   유니크 제약이 뒤늦게 잡아 주므로 그대로 500 을 내지 말고 다시 시도하게 한다.
        # ★유니크 위반만 409 로 변경한다. 외래키 위반 같은 다른 무결성 오류까지 삼키면
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


@router.post("/{run_id}/results/import")
def import_results(
    project_id: int,
    run_id: int,
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="true 면 계산만 하고 저장하지 않는다"),
    keep_executed: bool = Query(True, description="이미 기록된 결과를 미실행(NS)으로 덮어쓰지 않는다"),
    label: Optional[str] = Query(None, max_length=100, description="비고 앞머리. 비우면 형식 이름"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    """자동화 결과 파일(Playwright JSON · JUnit XML)을 이 수행의 결과로 기록한다.

    테스트 제목 맨 앞의 TC ID 로 행을 찾는다. 판정 규칙은 services/result_import.py.
    이슈 링크는 건드리지 않는다. 사람이 단 링크가 자동 기록으로 지워지면 안 된다.
    """
    _get_project_or_404(project_id, db)
    run = db.query(TestRun).filter(
        TestRun.id == run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    if run.status == TestRunStatus.completed:
        raise HTTPException(status_code=400, detail="완료된 테스트 런은 수정할 수 없습니다. 재오픈 후 수정하세요.")

    fmt, entries = _read_report(file)
    summary = _record_import(run, fmt, entries, db, current_user,
                             dry_run=dry_run, keep_executed=keep_executed, label=label)
    if not dry_run:
        db.commit()
    return summary


@router.post("/import")
def import_results_by_name(
    project_id: int,
    run_name: str = Query(..., max_length=200, description="수행 이름. 같은 이름의 회차에 이어 붙인다"),
    round_mode: str = Query("next", alias="round", pattern="^(next|open)$",
                       description="next: 다음 회차를 만든다. open: 진행 중인 회차가 있으면 거기에 기록한다"),
    version: Optional[str] = Query(None, max_length=50, description="새 회차의 버전. 비우면 직전 회차를 이어받는다"),
    environment: Optional[str] = Query(None, max_length=100, description="새 회차의 환경. 비우면 직전 회차를 이어받는다"),
    sheet_names: Optional[str] = Query(None, description="쉼표 구분 시트 이름. 주면 그 범위로 새 회차를 만든다"),
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="true 면 회차를 만들지 않고 계산만 한다"),
    keep_executed: bool = Query(True, description="이미 기록된 결과를 미실행(NS)으로 덮어쓰지 않는다"),
    label: Optional[str] = Query(None, max_length=100, description="비고 앞머리. 비우면 형식 이름"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
    _lock: None = Depends(project_write_lock),
):
    """수행 id 없이 이름으로 결과 파일을 올린다. CI 가 회차를 미리 만들어 둘 필요가 없게 한다.

    - 같은 이름의 수행이 있으면 최신 회차를 이어받아 다음 회차를 만든다(화면의 「다음 회차」 와 같다).
      버전 · 환경은 주면 그 값, 비우면 직전 회차 값이다.
    - round=open 이면 같은 이름의 진행 중인 회차에 기록한다. 스위트를 나눠 여러 번 올릴 때 쓴다.
      진행 중인 회차가 없으면 next 와 같다.
    - 같은 이름이 없으면 R1 을 만든다. 범위는 sheet_names, 없으면 프로젝트 전체.
    - dry_run 이면 같은 계산을 한 뒤 되돌린다. 회차는 남지 않는다.
    """
    _get_project_or_404(project_id, db)
    name = run_name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="수행 이름을 입력해 주세요.")
    # 회차를 만들기 전에 파일부터 읽는다. 깨진 파일로 빈 회차가 남지 않게.
    fmt, entries = _read_report(file)
    sheets = _validate_sheet_names(
        project_id, sheet_names.split(",") if sheet_names is not None else None, db,
    )

    latest_q = (
        db.query(TestRun)
        .filter(TestRun.project_id == project_id, TestRun.name == name)
        .order_by(TestRun.round.desc(), TestRun.created_at.desc(), TestRun.id.desc())
    )
    target = None
    if round_mode == "open":
        target = latest_q.filter(TestRun.status == TestRunStatus.in_progress).first()
    created = target is None
    if created:
        latest = latest_q.first()
        if latest is not None and sheets is None:
            target = _clone_run(latest, current_user, db, next_round=True)
        else:
            target = _new_run(
                project_id, current_user, db,
                name=name,
                version=latest.version if latest else None,
                environment=latest.environment if latest else None,
                round_=_max_round(project_id, name, db) + 1,
                test_plan_id=latest.test_plan_id if latest else None,
                sheet_names=sheets,
            )
        if version is not None:
            target.version = version.strip() or None
        if environment is not None:
            target.environment = environment.strip() or None
        db.flush()

    summary = _record_import(target, fmt, entries, db, current_user,
                             dry_run=dry_run, keep_executed=keep_executed, label=label)
    run_info = {
        "id": None if (dry_run and created) else target.id,
        "name": target.name,
        "round": target.round,
        "version": target.version,
        "environment": target.environment,
        "created": created,
    }
    if dry_run:
        # ★새 회차까지 만들어 같은 계산을 한 뒤 통째로 되돌린다. 미리보기가 실제 적용과 같은 경로를 탄다.
        db.rollback()
    else:
        db.commit()
    summary["run_id"] = run_info["id"]
    summary["run"] = run_info
    return summary


def _read_report(file: UploadFile):
    content = read_limited_sync(file.file, MAX_RESULT_IMPORT_SIZE)
    try:
        fmt, entries = parse_report(content, file.filename)
    except ImportFormatError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not entries:
        raise HTTPException(status_code=400, detail="파일에 테스트 결과가 없습니다.")
    return fmt, entries


def _record_import(run: TestRun, fmt: str, entries, db: Session, user: User, *,
                   dry_run: bool, keep_executed: bool, label: Optional[str]) -> dict:
    """판정 결과를 런의 행에 적는다. 커밋은 부른 쪽이 한다(dry_run 이면 적지 않는다)."""
    project_id, run_id = run.project_id, run.id
    # 저장·동기화와 같은 수행 잠금. keep_executed 판단은 잠금을 잡은 뒤의 값으로 한다.
    advisory_xact_lock(db, LockNs.RUN_RESULTS, run_id)
    # 런 생성 뒤에 추가된 TC 도 행이 있어야 기록된다. 상세 조회와 같은 보정을 먼저 한다.
    sync_run_results(run, db, commit=False)

    # 프로젝트의 TC 전체와 대조한다. 이 수행 범위 밖의 TC 는 매칭은 되지만 기록하지 않고 알려 준다.
    project_tcs = dict(
        db.query(TestCase.tc_id, TestCase.id).filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestCase.tc_id.isnot(None),
        ).all()
    )
    outcomes, unmatched = aggregate(entries, set(project_tcs))

    rows = {
        r.test_case_id: r for r in db.query(TestResult).filter(TestResult.test_run_id == run_id).all()
    }
    prefix = (label or "").strip() or f"자동 기록 ({FORMAT_LABEL[fmt]})"

    items, out_of_run, kept = [], [], []
    counts = {"PASS": 0, "FAIL": 0, "NS": 0}
    now = now_kst()
    for tc_id in sorted(outcomes):
        o = outcomes[tc_id]
        row = rows.get(project_tcs[tc_id])
        if row is None:
            out_of_run.append(tc_id)
            continue
        if keep_executed and o.result == "NS" and row.result != TestResultValue.NS:
            kept.append(tc_id)
            continue
        counts[o.result] += 1
        items.append({"tc_id": tc_id, "result": o.result, "kind": o.kind, "note": o.note})
        if dry_run:
            continue
        row.result = TestResultValue(o.result)
        row.actual_result = (o.actual or None) and o.actual[:1000]
        row.remarks = f"{prefix}. {o.note}" if o.note else prefix
        row.executed_by = user.id
        row.executed_at = now
        if o.duration_sec is not None:
            row.duration_sec = o.duration_sec

    return {
        "format": fmt,
        "dry_run": dry_run,
        "run_id": run_id,
        "total_tests": len(entries),
        "matched_tests": len(entries) - len(unmatched),
        "matched_tcs": len(outcomes),
        "recorded": len(items),
        "counts": counts,
        "items": items,
        "kept_executed": kept,
        "out_of_run": out_of_run,
        "fixed_candidates": [i["tc_id"] for i in items if i["kind"] == KIND_FIXED],
        "unexpected_failures": [i["tc_id"] for i in items if i["kind"] == KIND_FAIL],
        "known_failures": sum(1 for i in items if i["kind"] == KIND_KNOWN_FAIL),
        "unmatched_count": len(unmatched),
        "unmatched": unmatched[:MAX_UNMATCHED_LISTED],
    }


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

    # ★여기서 동기화하지 않는다. reopen 은 부르는데 complete 는 안 부르는 비대칭이
    #   빠뜨린 것처럼 보이지만, 완료는 "여기서 끝" 이라는 선언이다. 그 순간에 새 TC 를
    #   끌어들이면 수행하지 않은 행이 NS 로 들어가 합격률과 총계가 변경된다.
    #   reopen 이 부르는 것은 반대로 "다시 연다" 라서 그 사이 늘어난 TC 를 담아야 하기
    #   때문이다. TC 생성·복제·복원·임포트가 이미 진행 중 수행을 맞추므로
    #   (sync_project_in_progress_runs) 완료 직전에 누락이 남는 경로는 사실상 없다.
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
    next_round: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
    _lock: None = Depends(project_write_lock),
):
    """Clone an existing test run with all its test results reset to NS.

    next_round=true 면 "다음 회차" 다. 이름은 그대로 두고 회차를 같은 이름 가운데 가장 큰
    회차 + 1 로 정하며 플랜도 이어받는다. 예전 복제는 이름에 "(복제)" 가 붙고 회차가 그대로라
    다음 회차를 만들 때마다 둘 다 손으로 고쳐야 했다(09-30).
    """
    _get_project_or_404(project_id, db)

    source = (
        db.query(TestRun)
        .options(joinedload(TestRun.results))
        .filter(TestRun.id == run_id, TestRun.project_id == project_id)
        .first()
    )
    if not source:
        raise HTTPException(status_code=404, detail="Test run not found")

    new_run = _clone_run(source, current_user, db, next_round=next_round)
    db.commit()
    db.refresh(new_run)
    return new_run


def _max_round(project_id: int, name: str, db: Session) -> int:
    return (
        db.query(func.max(TestRun.round))
        .filter(TestRun.project_id == project_id, TestRun.name == name)
        .scalar()
    ) or 0


def _clone_run(source: TestRun, user: User, db: Session, *, next_round: bool) -> TestRun:
    """런 구조를 복제해 결과를 NS 로 둔 새 런을 만든다. 커밋은 부른 쪽이 한다."""
    if next_round:
        name, round_ = source.name, _max_round(source.project_id, source.name, db) + 1
    else:
        name, round_ = f"{source.name} (복제)", source.round
    new_run = TestRun(
        project_id=source.project_id,
        name=name,
        version=source.version,
        environment=source.environment,
        round=round_,
        sheet_names=source.sheet_names,
        test_plan_id=source.test_plan_id if next_round else None,
        created_by=user.id,
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
                "executed_by": user.id,
            })
        db.bulk_insert_mappings(TestResult, rows)
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
                TestCase.priority, TestCase.test_type, TestCase.precondition,
                TestCase.test_steps, TestCase.expected_result,
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

    # ★TC 에서 가져오는 열은 TC 관리 화면 차례를 따른다. 파일과 화면이 완전히 같지는
    #   않다. Type 은 파일에만, 첨부는 화면에만 있고 소요(초)는 타이머를 켠 화면에만
    #   나오는데 파일에는 늘 실린다. 사전조건과 Platform 자리는 수행 화면과 맞췄다.
    #   프로젝트 설정으로 숨긴 필드도 파일에는 실린다. 내보내기는 전체를 담는다.
    headers = ["No", "TC ID", "Type", "Category", "Depth1", "Depth2", "Priority",
               "Platform", "Precondition", "Test Steps", "Expected Result", "Result",
               "Actual Result", "Issue Link", "Duration(sec)", "Remarks"]
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
        ws.cell(row=row_idx, column=8, value=safe_cell(tc.test_type if tc else ""))
        ws.cell(row=row_idx, column=9, value=safe_cell(tc.precondition if tc else "")).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_idx, column=10, value=safe_cell(tc.test_steps if tc else "")).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_idx, column=11, value=safe_cell(tc.expected_result if tc else "")).alignment = Alignment(wrap_text=True)
        result_cell = ws.cell(row=row_idx, column=12, value=result_display)
        result_cell.alignment = Alignment(horizontal="center")
        if tr.result.value in result_fills:
            result_cell.fill = result_fills[tr.result.value]
        ws.cell(row=row_idx, column=13, value=safe_cell(tr.actual_result or "")).alignment = Alignment(wrap_text=True)
        ws.cell(row=row_idx, column=14, value=safe_cell(tr.issue_link or ""))
        ws.cell(row=row_idx, column=15, value=tr.duration_sec or "")
        ws.cell(row=row_idx, column=16, value=safe_cell(tr.remarks or "")).alignment = Alignment(wrap_text=True)

    # Auto-width (approximate)
    # ★headers 와 길이가 같아야 한다. 열을 끼우고 이 배열을 안 고치면 폭이 한 칸씩
    #   밀려 엉뚱한 열이 넓어진다(SYM-108 때 Precondition 을 넣고 놓쳤다).
    col_widths = [6, 12, 8, 14, 14, 14, 10, 12, 35, 40, 30, 10, 30, 20, 10, 20]
    assert len(col_widths) == len(headers), (
        f"열 폭 {len(col_widths)}개 != 헤더 {len(headers)}개"
    )
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
