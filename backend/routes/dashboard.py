from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import User, TestCase, TestRun, TestResult, TestResultValue
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/dashboard",
    tags=["dashboard"],
)


def _count_from_results(results: list) -> dict:
    """Count test results from TestResult records."""
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


def _get_all_results(project_id: int, db: Session) -> list:
    """전체(run_id 미지정) 시: 프로젝트의 모든 run 결과를 합산 반환.

    TODO: 대규모 프로젝트에서는 결과를 전부 메모리에 로드하므로 성능 이슈 가능.
          필요 시 DB 집계 쿼리로 최적화할 것.
    """
    run_ids = [
        r.id for r in db.query(TestRun.id)
        .filter(TestRun.project_id == project_id)
        .all()
    ]
    if not run_ids:
        return []

    return (
        db.query(TestResult)
        .filter(TestResult.test_run_id.in_(run_ids))
        .all()
    )


def _rates(counts: dict, total: int) -> dict:
    """Calculate percentage rates."""
    if total == 0:
        return {f"{k}_rate": 0.0 for k in counts}
    return {f"{k}_rate": round(v / total * 100, 1) for k, v in counts.items()}


# ── Summary ───────────────────────────────────────────────────────────────────

@router.get("/summary")
def dashboard_summary(
    project_id: int,
    run_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    total = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    ).count()

    if run_id:
        results = db.query(TestResult).filter(TestResult.test_run_id == run_id).all()
        if results:
            c = _count_from_results(results)
        else:
            c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}
        c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
        return {"total": total, **c, **_rates(c, total)}

    # 전체 모드: 모든 run의 결과를 합산
    results = _get_all_results(project_id, db)
    if results:
        c = _count_from_results(results)
    else:
        c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}
    total_results = c["pass"] + c["fail"] + c["block"] + c["na"] + c["not_started"]
    return {"total": total_results, **c, **_rates(c, total_results)}


# ── Priority Distribution ────────────────────────────────────────────────────

@router.get("/priority")
def priority_distribution(
    project_id: int,
    run_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    # 전체 모드: 모든 run 결과를 미리 조회
    if not run_id:
        all_results = _get_all_results(project_id, db)
        results_by_tc: dict[int, list] = {}
        for r in all_results:
            results_by_tc.setdefault(r.test_case_id, []).append(r)
    else:
        results_by_tc = None

    priorities = (
        db.query(TestCase.priority)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None), TestCase.priority.isnot(None))
        .distinct()
        .all()
    )

    result = []
    for (priority,) in priorities:
        tcs = db.query(TestCase).filter(
            TestCase.project_id == project_id, TestCase.priority == priority, TestCase.deleted_at.is_(None),
        ).all()
        tc_ids = [tc.id for tc in tcs]

        if run_id:
            results = db.query(TestResult).filter(
                TestResult.test_run_id == run_id,
                TestResult.test_case_id.in_(tc_ids),
            ).all()
            total = len(tcs)
            c = _count_from_results(results)
            c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
        else:
            results = [r for tid in tc_ids for r in results_by_tc.get(tid, [])]
            c = _count_from_results(results)
            total = c["pass"] + c["fail"] + c["block"] + c["na"] + c["not_started"]

        result.append({"priority": priority, "total": total, **c})

    return result


# ── Category Breakdown ────────────────────────────────────────────────────────

@router.get("/category")
def category_breakdown(
    project_id: int,
    run_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    if not run_id:
        all_results = _get_all_results(project_id, db)
        results_by_tc: dict[int, list] = {}
        for r in all_results:
            results_by_tc.setdefault(r.test_case_id, []).append(r)
    else:
        results_by_tc = None

    categories = (
        db.query(TestCase.category)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None), TestCase.category.isnot(None))
        .distinct()
        .all()
    )

    result = []
    for (category,) in categories:
        tcs = db.query(TestCase).filter(
            TestCase.project_id == project_id, TestCase.category == category, TestCase.deleted_at.is_(None),
        ).all()
        tc_ids = [tc.id for tc in tcs]

        if run_id:
            results = db.query(TestResult).filter(
                TestResult.test_run_id == run_id,
                TestResult.test_case_id.in_(tc_ids),
            ).all()
            total = len(tcs)
            c = _count_from_results(results)
            c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
        else:
            results = [r for tid in tc_ids for r in results_by_tc.get(tid, [])]
            c = _count_from_results(results)
            total = c["pass"] + c["fail"] + c["block"] + c["na"] + c["not_started"]

        result.append({"category": category, "total": total, **c})

    return result


# ── Round Comparison ──────────────────────────────────────────────────────────

@router.get("/rounds")
def round_comparison(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    total_tc = db.query(TestCase).filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None)).count()

    # Group TestRuns by round number
    runs = (
        db.query(TestRun)
        .filter(TestRun.project_id == project_id)
        .order_by(TestRun.round, TestRun.created_at.desc())
        .all()
    )

    # Use the latest run per round
    seen_rounds = {}
    for run in runs:
        if run.round not in seen_rounds:
            seen_rounds[run.round] = run

    result = []
    for round_num in sorted(seen_rounds.keys()):
        run = seen_rounds[round_num]
        results = db.query(TestResult).filter(TestResult.test_run_id == run.id).all()
        c = _count_from_results(results)

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
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    if not run_id:
        all_results = _get_all_results(project_id, db)
        results_by_tc: dict[int, list] = {}
        for r in all_results:
            results_by_tc.setdefault(r.test_case_id, []).append(r)
    else:
        results_by_tc = None

    assignees = (
        db.query(TestCase.assignee)
        .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None), TestCase.assignee.isnot(None))
        .distinct()
        .all()
    )

    result = []
    for (assignee,) in assignees:
        if not assignee or not assignee.strip():
            continue
        tcs = db.query(TestCase).filter(
            TestCase.project_id == project_id, TestCase.assignee == assignee, TestCase.deleted_at.is_(None),
        ).all()
        tc_ids = [tc.id for tc in tcs]

        if run_id:
            results = db.query(TestResult).filter(
                TestResult.test_run_id == run_id,
                TestResult.test_case_id.in_(tc_ids),
            ).all()
            total = len(tcs)
            c = _count_from_results(results)
            c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
        else:
            results = [r for tid in tc_ids for r in results_by_tc.get(tid, [])]
            c = _count_from_results(results)
            total = c["pass"] + c["fail"] + c["block"] + c["na"] + c["not_started"]

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

    # 전체 모드: 모든 run의 FAIL 결과를 합산
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
        )
        .group_by(TestCase.category, TestCase.priority)
        .all()
    )
    return [
        {"category": r.category or "", "priority": r.priority or "", "fail_count": r.fail_count}
        for r in query
    ]
