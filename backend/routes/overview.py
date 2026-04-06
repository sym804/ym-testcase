from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from database import get_db
from models import User, UserRole, Project, ProjectMember, TestCase, TestRun, TestResult, TestResultValue
from auth import get_current_user

router = APIRouter(
    prefix="/api/dashboard",
    tags=["overview"],
)


@router.get("/overview")
def global_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated dashboard across all projects the user can access."""
    all_projects = db.query(Project).all()

    if current_user.role in (UserRole.admin, UserRole.qa_manager):
        projects = all_projects
    else:
        member_project_ids = {
            m.project_id
            for m in db.query(ProjectMember.project_id)
            .filter(ProjectMember.user_id == current_user.id)
            .all()
        }
        projects = [
            p for p in all_projects
            if not p.is_private
            or p.id in member_project_ids
            or p.created_by == current_user.id
        ]

    project_ids = [p.id for p in projects]
    if not project_ids:
        return {
            "summary": {
                "total_projects": 0, "total_tc": 0,
                "pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": 0,
                "progress": 0.0, "pass_rate": 0.0,
            },
            "projects": [],
        }

    # 1) 프로젝트별 활성 TC 수 — 1회 SQL
    tc_counts = dict(
        db.query(TestCase.project_id, func.count(TestCase.id))
        .filter(TestCase.project_id.in_(project_ids), TestCase.deleted_at.is_(None))
        .group_by(TestCase.project_id)
        .all()
    )

    # 2) 프로젝트별 최신 TestRun ID — 서브쿼리 1회
    latest_run_sq = (
        db.query(
            TestRun.project_id,
            func.max(TestRun.id).label("max_run_id"),
        )
        .filter(TestRun.project_id.in_(project_ids))
        .group_by(TestRun.project_id)
        .subquery()
    )

    # 3) 최신 런의 결과를 SQL CASE 집계 — 1회 SQL
    # 활성 TC만 집계하기 위해 TestCase join + deleted_at IS NULL
    result_rows = (
        db.query(
            TestRun.project_id,
            func.sum(case((TestResult.result == TestResultValue.PASS, 1), else_=0)).label("p"),
            func.sum(case((TestResult.result == TestResultValue.FAIL, 1), else_=0)).label("f"),
            func.sum(case((TestResult.result == TestResultValue.BLOCK, 1), else_=0)).label("b"),
            func.sum(case((TestResult.result == TestResultValue.NA, 1), else_=0)).label("na"),
            func.count(TestResult.id).label("with_result"),
        )
        .join(latest_run_sq, TestRun.id == latest_run_sq.c.max_run_id)
        .join(TestResult, TestResult.test_run_id == TestRun.id)
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .filter(TestCase.deleted_at.is_(None))
        .group_by(TestRun.project_id)
        .all()
    )
    stats_by_project = {}
    for row in result_rows:
        stats_by_project[row.project_id] = {
            "pass": row.p or 0, "fail": row.f or 0,
            "block": row.b or 0, "na": row.na or 0,
            "with_result": row.with_result or 0,
        }

    total_tc = 0
    total_pass = 0
    total_fail = 0
    total_block = 0
    total_na = 0
    total_not_started = 0

    project_summaries = []

    for proj in projects:
        count = tc_counts.get(proj.id, 0)
        total_tc += count

        s = stats_by_project.get(proj.id)
        if s:
            p, f, b, na = s["pass"], s["fail"], s["block"], s["na"]
            ns = max(0, count - (p + f + b + na))
        else:
            p, f, b, na, ns = 0, 0, 0, 0, count

        total_pass += p
        total_fail += f
        total_block += b
        total_na += na
        total_not_started += ns

        done = count - ns
        progress = round(done / count * 100, 1) if count > 0 else 0.0
        pass_rate = round(p / (p + f + b) * 100, 1) if (p + f + b) > 0 else 0.0

        project_summaries.append({
            "id": proj.id,
            "name": proj.name,
            "total": count,
            "pass": p,
            "fail": f,
            "block": b,
            "na": na,
            "not_started": ns,
            "progress": progress,
            "pass_rate": pass_rate,
        })

    overall_done = total_tc - total_not_started
    overall_progress = round(overall_done / total_tc * 100, 1) if total_tc > 0 else 0.0
    executed = total_pass + total_fail + total_block
    overall_pass_rate = round(total_pass / executed * 100, 1) if executed > 0 else 0.0

    return {
        "summary": {
            "total_projects": len(projects),
            "total_tc": total_tc,
            "pass": total_pass,
            "fail": total_fail,
            "block": total_block,
            "na": total_na,
            "not_started": total_not_started,
            "progress": overall_progress,
            "pass_rate": overall_pass_rate,
        },
        "projects": project_summaries,
    }
