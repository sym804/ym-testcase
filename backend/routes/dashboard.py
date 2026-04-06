from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, case

from database import get_db
from models import User, TestCase, TestRun, TestResult, TestResultValue
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/dashboard",
    tags=["dashboard"],
)


# ── SQL 집계 헬퍼 ────────────────────────────────────────────────────────────

def _latest_run_subquery(project_id: int, db: Session, date_from: str = None, date_to: str = None):
    """TC별 최신 런의 test_run_id를 구하는 서브쿼리."""
    run_filter = [TestRun.project_id == project_id]
    if date_from:
        run_filter.append(TestRun.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        run_filter.append(TestRun.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))

    return (
        db.query(
            TestResult.test_case_id,
            func.max(TestResult.test_run_id).label("max_run_id"),
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(*run_filter)
        .group_by(TestResult.test_case_id)
        .subquery()
    )


def _result_count_cases():
    """SQL CASE 기반 결과 카운트 표현식 목록."""
    return {
        "pass": func.sum(case((TestResult.result == TestResultValue.PASS, 1), else_=0)),
        "fail": func.sum(case((TestResult.result == TestResultValue.FAIL, 1), else_=0)),
        "block": func.sum(case((TestResult.result == TestResultValue.BLOCK, 1), else_=0)),
        "na": func.sum(case((TestResult.result == TestResultValue.NA, 1), else_=0)),
        "ns": func.sum(case((TestResult.result == TestResultValue.NS, 1), else_=0)),
    }


def _counts_from_row(row, total: int) -> dict:
    """SQL 집계 결과 행을 dict로 변환."""
    c = {
        "pass": row.pass_count or 0,
        "fail": row.fail_count or 0,
        "block": row.block_count or 0,
        "na": row.na_count or 0,
        "not_started": 0,
    }
    c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
    return c


def _rates(counts: dict, total: int) -> dict:
    """Calculate percentage rates."""
    if total == 0:
        return {f"{k}_rate": 0.0 for k in counts}
    return {f"{k}_rate": round(v / total * 100, 1) for k, v in counts.items()}


def _count_from_results(results: list) -> dict:
    """Count test results from TestResult records (run_id 지정 시 사용)."""
    counts = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": 0}
    for r in results:
        val = r.result.value if hasattr(r.result, "value") else str(r.result)
        if val == "PASS":
            counts["pass"] += 1
        elif val == "FAIL":
            counts["fail"] += 1
        elif val == "BLOCK":
            counts["block"] += 1
        elif val in ("NA", "N/A"):
            counts["na"] += 1
        elif val == "NS":
            counts["not_started"] += 1
        else:
            counts["not_started"] += 1
    return counts


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary")
def dashboard_summary(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    total = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).count()

    if run_id:
        cases = _result_count_cases()
        row = db.query(
            cases["pass"].label("pass_count"),
            cases["fail"].label("fail_count"),
            cases["block"].label("block_count"),
            cases["na"].label("na_count"),
        ).filter(TestResult.test_run_id == run_id).first()
        if row and (row.pass_count or row.fail_count or row.block_count or row.na_count):
            c = _counts_from_row(row, total)
        else:
            c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}
        return {"total": total, **c, **_rates(c, total)}

    # 전체 모드: SQL 집계로 TC별 최신 결과 카운트
    latest = _latest_run_subquery(project_id, db, date_from, date_to)
    cases = _result_count_cases()
    row = (
        db.query(
            cases["pass"].label("pass_count"),
            cases["fail"].label("fail_count"),
            cases["block"].label("block_count"),
            cases["na"].label("na_count"),
        )
        .join(
            latest,
            and_(
                TestResult.test_case_id == latest.c.test_case_id,
                TestResult.test_run_id == latest.c.max_run_id,
            ),
        )
        .first()
    )
    if row and (row.pass_count or row.fail_count or row.block_count or row.na_count):
        c = _counts_from_row(row, total)
    else:
        c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}
    return {"total": total, **c, **_rates(c, total)}


# ── Priority Distribution ────────────────────────────────────────────────────

@router.get("/priority")
def priority_distribution(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    # TC priority별 총 건수
    priority_totals = dict(
        db.query(TestCase.priority, func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestCase.priority.isnot(None),
        )
        .group_by(TestCase.priority)
        .all()
    )
    if not priority_totals:
        return []

    cases = _result_count_cases()

    if run_id:
        rows = (
            db.query(
                TestCase.priority,
                cases["pass"].label("pass_count"),
                cases["fail"].label("fail_count"),
                cases["block"].label("block_count"),
                cases["na"].label("na_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.priority.isnot(None),
                TestResult.test_run_id == run_id,
            )
            .group_by(TestCase.priority)
            .all()
        )
    else:
        latest = _latest_run_subquery(project_id, db, date_from, date_to)
        rows = (
            db.query(
                TestCase.priority,
                cases["pass"].label("pass_count"),
                cases["fail"].label("fail_count"),
                cases["block"].label("block_count"),
                cases["na"].label("na_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .join(
                latest,
                and_(
                    TestResult.test_case_id == latest.c.test_case_id,
                    TestResult.test_run_id == latest.c.max_run_id,
                ),
            )
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.priority.isnot(None),
            )
            .group_by(TestCase.priority)
            .all()
        )

    counts_map = {}
    for row in rows:
        total = priority_totals.get(row.priority, 0)
        counts_map[row.priority] = _counts_from_row(row, total)

    result = []
    for priority in sorted(priority_totals.keys()):
        total = priority_totals[priority]
        c = counts_map.get(priority, {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total})
        result.append({"priority": priority, "total": total, **c})

    return result


# ── Category Breakdown ────────────────────────────────────────────────────────

@router.get("/category")
def category_breakdown(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    category_totals = dict(
        db.query(TestCase.category, func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestCase.category.isnot(None),
        )
        .group_by(TestCase.category)
        .all()
    )
    if not category_totals:
        return []

    cases = _result_count_cases()

    if run_id:
        rows = (
            db.query(
                TestCase.category,
                cases["pass"].label("pass_count"),
                cases["fail"].label("fail_count"),
                cases["block"].label("block_count"),
                cases["na"].label("na_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.category.isnot(None),
                TestResult.test_run_id == run_id,
            )
            .group_by(TestCase.category)
            .all()
        )
    else:
        latest = _latest_run_subquery(project_id, db, date_from, date_to)
        rows = (
            db.query(
                TestCase.category,
                cases["pass"].label("pass_count"),
                cases["fail"].label("fail_count"),
                cases["block"].label("block_count"),
                cases["na"].label("na_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .join(
                latest,
                and_(
                    TestResult.test_case_id == latest.c.test_case_id,
                    TestResult.test_run_id == latest.c.max_run_id,
                ),
            )
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.category.isnot(None),
            )
            .group_by(TestCase.category)
            .all()
        )

    counts_map = {}
    for row in rows:
        total = category_totals.get(row.category, 0)
        counts_map[row.category] = _counts_from_row(row, total)

    result = []
    for category in sorted(category_totals.keys()):
        total = category_totals[category]
        c = counts_map.get(category, {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total})
        result.append({"category": category, "total": total, **c})

    return result


# ── Round Comparison ──────────────────────────────────────────────────────────

@router.get("/rounds")
def round_comparison(
    project_id: int,
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    total_tc = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None)).count()

    # Group TestRuns by round number
    run_q = db.query(TestRun).filter(TestRun.project_id == project_id)
    if date_from:
        run_q = run_q.filter(TestRun.created_at >= datetime.fromisoformat(date_from))
    if date_to:
        run_q = run_q.filter(TestRun.created_at <= datetime.fromisoformat(date_to + "T23:59:59"))
    runs = run_q.order_by(TestRun.round, TestRun.created_at.desc()).all()

    # Use the latest run per round
    seen_rounds = {}
    for run in runs:
        if run.round not in seen_rounds:
            seen_rounds[run.round] = run

    if not seen_rounds:
        return []

    # 모든 라운드의 결과를 SQL 집계로 한 번에 카운트
    run_ids = [run.id for run in seen_rounds.values()]
    cases = _result_count_cases()
    rows = (
        db.query(
            TestResult.test_run_id,
            cases["pass"].label("pass_count"),
            cases["fail"].label("fail_count"),
            cases["block"].label("block_count"),
            cases["na"].label("na_count"),
        )
        .filter(TestResult.test_run_id.in_(run_ids))
        .group_by(TestResult.test_run_id)
        .all()
    )

    counts_by_run = {}
    for row in rows:
        c = _counts_from_row(row, total_tc)
        counts_by_run[row.test_run_id] = c

    result = []
    for round_num in sorted(seen_rounds.keys()):
        run = seen_rounds[round_num]
        c = counts_by_run.get(run.id, {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total_tc})

        executed = c["pass"] + c["fail"] + c["block"]
        pass_rate = round(c["pass"] / executed * 100, 1) if executed > 0 else 0.0

        result.append({
            "round": round_num, "total": total_tc,
            **c, "pass_rate": pass_rate,
        })

    return result


# ── Assignee Summary ──────────────────────────────────────────────────────────

@router.get("/assignee")
def assignee_summary(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    assignee_totals = dict(
        db.query(TestCase.assignee, func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestCase.assignee.isnot(None),
            func.trim(TestCase.assignee) != "",
        )
        .group_by(TestCase.assignee)
        .all()
    )
    if not assignee_totals:
        return []

    cases = _result_count_cases()

    if run_id:
        rows = (
            db.query(
                TestCase.assignee,
                cases["pass"].label("pass_count"),
                cases["fail"].label("fail_count"),
                cases["block"].label("block_count"),
                cases["na"].label("na_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.assignee.isnot(None),
                func.trim(TestCase.assignee) != "",
                TestResult.test_run_id == run_id,
            )
            .group_by(TestCase.assignee)
            .all()
        )
    else:
        latest = _latest_run_subquery(project_id, db, date_from, date_to)
        rows = (
            db.query(
                TestCase.assignee,
                cases["pass"].label("pass_count"),
                cases["fail"].label("fail_count"),
                cases["block"].label("block_count"),
                cases["na"].label("na_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .join(
                latest,
                and_(
                    TestResult.test_case_id == latest.c.test_case_id,
                    TestResult.test_run_id == latest.c.max_run_id,
                ),
            )
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestCase.assignee.isnot(None),
                func.trim(TestCase.assignee) != "",
            )
            .group_by(TestCase.assignee)
            .all()
        )

    counts_map = {}
    for row in rows:
        total = assignee_totals.get(row.assignee, 0)
        counts_map[row.assignee] = _counts_from_row(row, total)

    result = []
    for assignee in sorted(assignee_totals.keys()):
        total = assignee_totals[assignee]
        c = counts_map.get(assignee, {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total})

        done = total - c["not_started"]
        completion_rate = round(done / total * 100, 1) if total > 0 else 0.0

        result.append({
            "assignee": assignee, "total": total,
            **c, "completion_rate": completion_rate,
        })

    return result


@router.get("/heatmap")
def get_heatmap(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """Category x Priority FAIL heatmap data."""

    if run_id:
        query = (
            db.query(
                TestCase.category,
                TestCase.priority,
                func.count().label("fail_count"),
            )
            .join(TestResult, TestResult.test_case_id == TestCase.id)
            .filter(
                TestCase.project_id == project_id,
                TestCase.deleted_at.is_(None),
                TestResult.result == TestResultValue.FAIL,
                TestResult.test_run_id == run_id,
            )
            .group_by(TestCase.category, TestCase.priority)
            .all()
        )
        return [
            {"category": r.category or "", "priority": r.priority or "", "fail_count": r.fail_count}
            for r in query
        ]

    # 전체 모드: TC별 최신 런 결과 기준 FAIL만 집계
    latest = _latest_run_subquery(project_id, db, date_from, date_to)
    query = (
        db.query(
            TestCase.category,
            TestCase.priority,
            func.count().label("fail_count"),
        )
        .join(TestResult, TestResult.test_case_id == TestCase.id)
        .join(
            latest,
            and_(
                TestResult.test_case_id == latest.c.test_case_id,
                TestResult.test_run_id == latest.c.max_run_id,
            ),
        )
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestResult.result == TestResultValue.FAIL,
        )
        .group_by(TestCase.category, TestCase.priority)
        .all()
    )
    return [
        {"category": r.category or "", "priority": r.priority or "", "fail_count": r.fail_count}
        for r in query
    ]
