from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

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
    """전체(run_id 미지정) 시: TC별 최신 런의 결과만 반환.

    DB 서브쿼리로 TC별 가장 최신 런의 result_id를 구하고,
    해당 결과만 조회한다. 런이 많아도 성능 OK.
    """
    # 서브쿼리: TC별 최신 런의 test_run_id
    latest_run_per_tc = (
        db.query(
            TestResult.test_case_id,
            func.max(TestResult.test_run_id).label("max_run_id"),
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(TestRun.project_id == project_id)
        .group_by(TestResult.test_case_id)
        .subquery()
    )

    # 최신 런의 결과만 조회
    return (
        db.query(TestResult)
        .join(
            latest_run_per_tc,
            and_(
                TestResult.test_case_id == latest_run_per_tc.c.test_case_id,
                TestResult.test_run_id == latest_run_per_tc.c.max_run_id,
            ),
        )
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

    # 전체 모드: TC별 최신 결과 기준
    results = _get_all_results(project_id, db)
    if results:
        c = _count_from_results(results)
    else:
        c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}
    c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
    return {"total": total, **c, **_rates(c, total)}


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

    # TC를 한 번에 조회 후 메모리에서 그룹핑 (N+1 방지)
    all_tcs = db.query(TestCase).filter(
        TestCase.project_id == project_id, TestCase.deleted_at.is_(None), TestCase.priority.isnot(None),
    ).all()

    tcs_by_priority: dict[str, list] = {}
    for tc in all_tcs:
        tcs_by_priority.setdefault(tc.priority, []).append(tc)

    # run_id가 있으면 해당 런 결과도 한 번에 조회
    run_results_by_tc: dict[int, TestResult] = {}
    if run_id:
        all_tc_ids = [tc.id for tc in all_tcs]
        if all_tc_ids:
            for r in db.query(TestResult).filter(
                TestResult.test_run_id == run_id,
                TestResult.test_case_id.in_(all_tc_ids),
            ).all():
                run_results_by_tc[r.test_case_id] = r

    result = []
    for priority, tcs in sorted(tcs_by_priority.items()):
        tc_ids = [tc.id for tc in tcs]
        total = len(tcs)

        if run_id:
            results = [run_results_by_tc[tid] for tid in tc_ids if tid in run_results_by_tc]
        else:
            results = [r for tid in tc_ids for r in results_by_tc.get(tid, [])]

        c = _count_from_results(results)
        c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
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

    # TC를 한 번에 조회 후 메모리에서 그룹핑 (N+1 방지)
    all_tcs = db.query(TestCase).filter(
        TestCase.project_id == project_id, TestCase.deleted_at.is_(None), TestCase.category.isnot(None),
    ).all()

    tcs_by_category: dict[str, list] = {}
    for tc in all_tcs:
        tcs_by_category.setdefault(tc.category, []).append(tc)

    run_results_by_tc: dict[int, TestResult] = {}
    if run_id:
        all_tc_ids = [tc.id for tc in all_tcs]
        if all_tc_ids:
            for r in db.query(TestResult).filter(
                TestResult.test_run_id == run_id,
                TestResult.test_case_id.in_(all_tc_ids),
            ).all():
                run_results_by_tc[r.test_case_id] = r

    result = []
    for category, tcs in sorted(tcs_by_category.items()):
        tc_ids = [tc.id for tc in tcs]
        total = len(tcs)

        if run_id:
            results = [run_results_by_tc[tid] for tid in tc_ids if tid in run_results_by_tc]
        else:
            results = [r for tid in tc_ids for r in results_by_tc.get(tid, [])]

        c = _count_from_results(results)
        c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))
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

    # 모든 라운드의 결과를 한 번에 조회 (N+1 방지)
    run_ids = [run.id for run in seen_rounds.values()]
    all_results = db.query(TestResult).filter(
        TestResult.test_run_id.in_(run_ids)
    ).all() if run_ids else []

    results_by_run: dict[int, list] = {}
    for r in all_results:
        results_by_run.setdefault(r.test_run_id, []).append(r)

    result = []
    for round_num in sorted(seen_rounds.keys()):
        run = seen_rounds[round_num]
        results = results_by_run.get(run.id, [])
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

    # TC를 한 번에 조회 후 메모리에서 그룹핑 (N+1 방지)
    all_tcs = db.query(TestCase).filter(
        TestCase.project_id == project_id, TestCase.deleted_at.is_(None), TestCase.assignee.isnot(None),
    ).all()

    tcs_by_assignee: dict[str, list] = {}
    for tc in all_tcs:
        if tc.assignee and tc.assignee.strip():
            tcs_by_assignee.setdefault(tc.assignee, []).append(tc)

    run_results_by_tc: dict[int, TestResult] = {}
    if run_id:
        all_tc_ids = [tc.id for tc in all_tcs]
        if all_tc_ids:
            for r in db.query(TestResult).filter(
                TestResult.test_run_id == run_id,
                TestResult.test_case_id.in_(all_tc_ids),
            ).all():
                run_results_by_tc[r.test_case_id] = r

    result = []
    for assignee, tcs in sorted(tcs_by_assignee.items()):
        tc_ids = [tc.id for tc in tcs]
        total = len(tcs)

        if run_id:
            results = [run_results_by_tc[tid] for tid in tc_ids if tid in run_results_by_tc]
        else:
            results = [r for tid in tc_ids for r in results_by_tc.get(tid, [])]

        c = _count_from_results(results)
        c["not_started"] = max(0, total - (c["pass"] + c["fail"] + c["block"] + c["na"]))

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
