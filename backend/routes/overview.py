"""메인 화면 전체 현황 (SYM-225)

진행 중 수행과 최근 완료 수행을 따로 센다. 예전에는 프로젝트마다 id 가 가장 큰 수행 하나로
세어, 새 회차를 만들기만 해도 그 프로젝트가 진행률 0% 로 떨어지고 어느 수행의 숫자인지도
보이지 않았다. 서로 다른 수행을 섞어 더한 진행률 · 합격률도 뜻이 없어 요약에서 뺐다.

수치는 지금 남은 TC 기준이다(지운 TC 제외). 대시보드의 수행 보기와 같은 기준이다
(services/tc_snapshot.py 머리 주석). 합격률은 판정(PASS/FAIL/BLOCK)이 없으면 None(SYM-133).
"""
from fastapi import APIRouter, Depends
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session

from auth import get_current_user
from database import get_db
from models import (
    Project, ProjectMember, TestCase, TestResult, TestResultValue, TestRun, TestRunStatus, User, UserRole,
)

router = APIRouter(
    prefix="/api/dashboard",
    tags=["overview"],
)


def visible_projects(db: Session, user: User) -> list[Project]:
    """이 사용자가 메인 화면에서 볼 프로젝트. 관리자 · QA 매니저는 전부, 그 밖은 공개 + 멤버."""
    q = db.query(Project)
    if user.role not in (UserRole.admin, UserRole.qa_manager):
        member_ids = db.query(ProjectMember.project_id).filter(ProjectMember.user_id == user.id)
        q = q.filter(or_(Project.is_private.is_(False), Project.id.in_(member_ids)))
    # 최근에 만든 프로젝트가 위다(프로젝트 목록 API 와 같은 순서).
    return q.order_by(Project.created_at.desc(), Project.id.desc()).all()


def _run_stats(db: Session, run_ids: list[int]) -> dict[int, dict]:
    """수행별 결과 집계(한 번). 지금 남은 TC 의 결과 행만 센다."""
    if not run_ids:
        return {}
    is_ = lambda v: func.sum(case((TestResult.result == v, 1), else_=0))  # noqa: E731
    rows = (
        db.query(
            TestResult.test_run_id,
            func.count(TestResult.id),
            is_(TestResultValue.PASS), is_(TestResultValue.FAIL),
            is_(TestResultValue.BLOCK), is_(TestResultValue.NA), is_(TestResultValue.NS),
        )
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .filter(TestResult.test_run_id.in_(run_ids), TestCase.deleted_at.is_(None))
        .group_by(TestResult.test_run_id)
        .all()
    )
    out = {}
    for run_id, total, p, f, b, na, ns in rows:
        out[run_id] = {"total": int(total), "pass": int(p or 0), "fail": int(f or 0),
                       "block": int(b or 0), "na": int(na or 0), "ns": int(ns or 0)}
    return out


def _run_summary(run: TestRun, stats: dict | None, project_name: str) -> dict:
    s = stats or {"total": 0, "pass": 0, "fail": 0, "block": 0, "na": 0, "ns": 0}
    total = s["total"]
    executed = total - s["ns"]
    judged = s["pass"] + s["fail"] + s["block"]
    return {
        "project_id": run.project_id,
        "project_name": project_name,
        "run_id": run.id,
        "name": run.name,
        "round": run.round or 1,
        "version": run.version,
        "environment": run.environment,
        "status": run.status.value if hasattr(run.status, "value") else run.status,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "total": total,
        "executed": executed,
        "pass": s["pass"],
        "fail": s["fail"],
        "block": s["block"],
        "na": s["na"],
        # 분모는 그 수행이 담은 행 수다. 시트를 골라 만든 수행도 다 하면 100% 다.
        "progress": round(executed / total * 100, 1) if total else 0.0,
        "pass_rate": round(s["pass"] / judged * 100, 1) if judged else None,
    }


@router.get("/overview")
def global_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = visible_projects(db, current_user)
    project_ids = [p.id for p in projects]
    names = {p.id: p.name for p in projects}

    tc_counts = dict(
        db.query(TestCase.project_id, func.count(TestCase.id))
        .filter(TestCase.project_id.in_(project_ids), TestCase.deleted_at.is_(None))
        .group_by(TestCase.project_id)
        .all()
    ) if project_ids else {}

    active = (
        db.query(TestRun)
        .filter(TestRun.project_id.in_(project_ids), TestRun.status == TestRunStatus.in_progress)
        .order_by(TestRun.created_at.desc(), TestRun.id.desc())
        .all()
    ) if project_ids else []

    # 프로젝트별 마지막 완료 수행. 만든 순서가 아니라 완료한 시각으로 고른다(같으면 id 가 큰 것).
    last_done: dict[int, TestRun] = {}
    if project_ids:
        ranked = (
            db.query(
                TestRun.id,
                func.row_number().over(
                    partition_by=TestRun.project_id,
                    order_by=(TestRun.completed_at.desc().nulls_last(), TestRun.id.desc()),
                ).label("rk"),
            )
            .filter(TestRun.project_id.in_(project_ids), TestRun.status == TestRunStatus.completed)
            .subquery()
        )
        for run in db.query(TestRun).join(ranked, and_(TestRun.id == ranked.c.id, ranked.c.rk == 1)).all():
            last_done[run.project_id] = run

    stats = _run_stats(db, [r.id for r in active] + [r.id for r in last_done.values()])

    active_runs = [_run_summary(r, stats.get(r.id), names[r.project_id]) for r in active]
    by_project: dict[int, list[dict]] = {}
    for r in active_runs:
        by_project.setdefault(r["project_id"], []).append(r)

    project_rows = []
    for p in projects:
        done = last_done.get(p.id)
        project_rows.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "is_private": bool(p.is_private),
            "created_at": p.created_at,
            "active_tc": tc_counts.get(p.id, 0),
            "in_progress": by_project.get(p.id, []),
            "last_completed": _run_summary(done, stats.get(done.id), p.name) if done else None,
        })

    return {
        "summary": {
            "total_projects": len(projects),
            "active_tc": sum(tc_counts.values()),
            "in_progress_runs": len(active_runs),
            "in_progress_fail_block": sum(r["fail"] + r["block"] for r in active_runs),
        },
        "active_runs": active_runs,
        "projects": project_rows,
    }
