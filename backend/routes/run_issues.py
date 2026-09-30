"""수행별 이슈 목록. 리포트의 이슈 섹션이 이것을 싣는다.

이슈 관리 도구와 연동하지 않는다. 사람이 화면에서 넣거나, MCP 같은 도구가 이
API 로 채운다. 같은 주소는 한 수행에 한 번만 들어간다(409). 채우는 쪽이 같은
목록을 다시 보내도 중복이 쌓이지 않는다.

완료된 수행에도 넣고 고칠 수 있다. 이슈는 보통 수행을 마친 뒤 리포트를 쓰면서
정리하기 때문이다.

이전 회차 이슈는 carry-over 로 가져온다. 가져온 이슈는 발견 수행(origin)이 그
회차를 가리키고 판정(verdict)은 미확인으로 시작한다. QA 가 이번 수행에서 재현해
보고 해결 · 유지 · 부분 해결로 판정하면 리포트가 처리 완료 · 미처리로 나눈다.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import check_project_access
from database import get_db
from models import RunIssue, TestCase, TestResult, TestRun, User
from schemas import (
    RunIssueCarryOver, RunIssueCarryOverResult, RunIssueCreate, RunIssueResponse, RunIssueUpdate,
)
from services.issue_key import extract_issue_key

router = APIRouter(
    prefix="/api/projects/{project_id}/testruns/{run_id}/issues",
    tags=["run-issues"],
)

DUPLICATE_DETAIL = "Issue already added to this run"


def _get_run_or_404(project_id: int, run_id: int, db: Session) -> TestRun:
    run = db.query(TestRun).filter(TestRun.id == run_id, TestRun.project_id == project_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


def _get_issue_or_404(run_id: int, issue_id: int, db: Session) -> RunIssue:
    issue = db.query(RunIssue).filter(RunIssue.id == issue_id, RunIssue.test_run_id == run_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


def _resolve_test_cases(db: Session, run_id: int, tc_ids: list[str], strict: bool = True) -> list[TestCase]:
    """TC-ID 를 이 수행에 담긴 TC 로 변경한다. 없는 것이 하나라도 있으면 422.

    수행 밖의 TC 는 받지 않는다. 리포트는 이번 수행의 기록이라, 다른 TC 가 섞이면
    읽는 쪽이 어디서 나온 TC 인지 알 수 없다. 같은 TC-ID 가 둘이면(지운 TC 와 새 TC)
    지우지 않은 쪽을 쓴다. strict=False 면 없는 TC 는 조용히 뺀다(이전 회차에서
    가져올 때. 이번 수행에 없는 TC 는 연결할 수 없다).
    """
    if not tc_ids:
        return []
    rows = (
        db.query(TestCase)
        .join(TestResult, TestResult.test_case_id == TestCase.id)
        .filter(TestResult.test_run_id == run_id, TestCase.tc_id.in_(tc_ids))
        .all()
    )
    by_id: dict[str, TestCase] = {}
    for tc in rows:
        if tc.tc_id not in by_id or (by_id[tc.tc_id].deleted_at is not None and tc.deleted_at is None):
            by_id[tc.tc_id] = tc
    missing = [t for t in tc_ids if t not in by_id]
    if missing and strict:
        raise HTTPException(status_code=422, detail=f"TC not in this run: {', '.join(missing)}")
    return [by_id[t] for t in tc_ids if t in by_id]


def _resolve_origin(db: Session, run: TestRun, origin_run_id: int | None) -> TestRun | None:
    """발견 수행. 같은 프로젝트의 다른 수행이어야 한다. 아니면 422."""
    if origin_run_id is None:
        return None
    if origin_run_id == run.id:
        raise HTTPException(status_code=422, detail="origin_run_id must be another run")
    origin = db.query(TestRun).filter(TestRun.id == origin_run_id, TestRun.project_id == run.project_id).first()
    if origin is None:
        raise HTTPException(status_code=422, detail="origin_run_id not in this project")
    return origin


def _duplicate(db: Session, run_id: int, url: str, exclude_id: int | None = None) -> bool:
    q = db.query(RunIssue.id).filter(RunIssue.test_run_id == run_id, RunIssue.url == url)
    if exclude_id is not None:
        q = q.filter(RunIssue.id != exclude_id)
    return q.first() is not None


@router.get("", response_model=List[RunIssueResponse])
def list_run_issues(
    project_id: int,
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    run = _get_run_or_404(project_id, run_id, db)
    return run.issues


@router.post("", response_model=RunIssueResponse, status_code=status.HTTP_201_CREATED)
def create_run_issue(
    project_id: int,
    run_id: int,
    payload: RunIssueCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    run = _get_run_or_404(project_id, run_id, db)
    if _duplicate(db, run_id, payload.url):
        raise HTTPException(status_code=409, detail=DUPLICATE_DETAIL)
    test_cases = _resolve_test_cases(db, run_id, payload.tc_ids)
    origin = _resolve_origin(db, run, payload.origin_run_id)

    issue = RunIssue(
        test_run_id=run_id,
        title=payload.title,
        url=payload.url,
        issue_key=payload.issue_key or extract_issue_key(payload.url),
        status=payload.status,
        note=payload.note,
        origin_run_id=origin.id if origin else None,
        origin_round=origin.round if origin else None,
        verdict=payload.verdict,
        created_by=current_user.id,
        test_cases=test_cases,
    )
    db.add(issue)
    try:
        db.commit()
    except IntegrityError:
        # 조회와 삽입 사이에 같은 주소가 먼저 들어간 경우. 유니크 인덱스가 막는다.
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_DETAIL)
    db.refresh(issue)
    return issue


@router.put("/{issue_id}", response_model=RunIssueResponse)
def update_run_issue(
    project_id: int,
    run_id: int,
    issue_id: int,
    payload: RunIssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    run = _get_run_or_404(project_id, run_id, db)
    issue = _get_issue_or_404(run_id, issue_id, db)
    data = payload.model_dump(exclude_unset=True)

    if "origin_run_id" in data:
        # null 은 신규 이슈로 되돌린다. 발견 회차도 같이 비운다.
        origin = _resolve_origin(db, run, data.pop("origin_run_id"))
        issue.origin_run_id = origin.id if origin else None
        issue.origin_round = origin.round if origin else None

    if "title" in data and not data["title"]:
        raise HTTPException(status_code=422, detail="title must not be empty")
    if "url" in data:
        if data["url"] is None:
            raise HTTPException(status_code=422, detail="url must not be empty")
        if _duplicate(db, run_id, data["url"], exclude_id=issue.id):
            raise HTTPException(status_code=409, detail=DUPLICATE_DETAIL)

    if "tc_ids" in data:
        issue.test_cases = _resolve_test_cases(db, run_id, data.pop("tc_ids") or [])

    # 키가 옛 주소에서 뽑은 값이면 주소를 변경할 때 따라 변경한다. 손으로 적은 키는 둔다.
    key_was_derived = issue.issue_key == extract_issue_key(issue.url)
    for key, value in data.items():
        setattr(issue, key, value)
    if "issue_key" not in data and "url" in data and key_was_derived:
        issue.issue_key = None
    if not issue.issue_key:
        issue.issue_key = extract_issue_key(issue.url)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE_DETAIL)
    db.refresh(issue)
    return issue


@router.post("/carry-over", response_model=RunIssueCarryOverResult)
def carry_over_run_issues(
    project_id: int,
    run_id: int,
    payload: RunIssueCarryOver | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    """이전 회차의 이슈를 이 수행으로 가져온다.

    출처를 비우면 리포트의 비교 대상(compare_run_id, 없으면 같은 이름의 이전 회차)이다.
    비교 대상이 없으면 404. 같은 주소가 이미 있는 이슈는 건너뛴다(skipped). 가져온
    이슈는 발견 수행이 출처(출처도 가져온 것이면 그 원래 수행)를 가리키고 판정은
    미확인이다. 연관 TC 는 이 수행에 담긴 것만 잇는다.
    """
    from routes.reports import _compare_target

    run = _get_run_or_404(project_id, run_id, db)
    from_run_id = payload.from_run_id if payload else None
    if from_run_id is not None:
        source = _resolve_origin(db, run, from_run_id)
    else:
        source, _mode = _compare_target(run, db)
        if source is None:
            raise HTTPException(status_code=404, detail="No previous run to carry over from")

    existing = {u for (u,) in db.query(RunIssue.url).filter(RunIssue.test_run_id == run.id)}
    added: list[RunIssue] = []
    skipped = 0
    for src in source.issues:
        if src.url in existing:
            skipped += 1
            continue
        issue = RunIssue(
            test_run_id=run.id,
            title=src.title,
            url=src.url,
            issue_key=src.issue_key,
            status=src.status,
            note=src.note,
            origin_run_id=src.origin_run_id or source.id,
            origin_round=src.origin_round if src.origin_round is not None else source.round,
            verdict="unverified",
            created_by=current_user.id,
            test_cases=_resolve_test_cases(db, run.id, src.tc_ids, strict=False),
        )
        db.add(issue)
        added.append(issue)
        existing.add(src.url)
    db.commit()
    for issue in added:
        db.refresh(issue)
    return RunIssueCarryOverResult(
        from_run_id=source.id, from_run_name=source.name, from_run_round=source.round,
        added=len(added), skipped=skipped, issues=added,
    )


@router.delete("/{issue_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run_issue(
    project_id: int,
    run_id: int,
    issue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("tester")),
):
    _get_run_or_404(project_id, run_id, db)
    issue = _get_issue_or_404(run_id, issue_id, db)
    db.delete(issue)
    db.commit()
