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
    """전체(run_id 미지정) 시: TC별 최신 런의 결과만 반환.

    같은 TC가 여러 런에 존재할 경우, 가장 최근 런의 결과를 사용한다.
    """
    run_ids = [
        r.id for r in db.query(TestRun.id)
        .filter(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
        .all()
    ]
    if not run_ids:
        return []

    all_results = (
        db.query(TestResult)
        .filter(TestResult.test_run_id.in_(run_ids))
        .all()
    )

    # TC별 최신 결과만 남기기 (run_ids는 최신순이므로 먼저 나온 게 최신)
    seen_tc_ids: set[int] = set()
    latest_results: list = []
    # run_ids 순서대로 (최신 런 우선) 결과를 필터
    run_order = {rid: i for i, rid in enumerate(run_ids)}
    all_results.sort(key=lambda r: run_order.get(r.test_run_id, 999999))
    for r in all_results:
        if r.test_case_id not in seen_tc_ids:
            seen_tc_ids.add(r.test_case_id)
            latest_results.append(r)

    return latest_results


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
            total = len(tcs)
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
            total = len(tcs)
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
            total = len(tcs)
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
