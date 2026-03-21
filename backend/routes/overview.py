from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole, Project, ProjectMember, TestCase, TestRun, TestResult
from auth import get_current_user

router = APIRouter(
    prefix="/api/dashboard",
    tags=["overview"],
)


def _get_latest_run_for_project(project_id: int, db: Session):
    """Get the latest TestRun for a project."""
    return (
        db.query(TestRun)
        .filter(TestRun.project_id == project_id)
        .order_by(TestRun.created_at.desc())
        .first()
    )


def _count_results(results: list) -> dict:
    """Count results from TestResult records."""
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
        else:
            counts["not_started"] += 1
    return counts


@router.get("/overview")
def global_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return aggregated dashboard across all projects the user can access.

    Rules (consistent with get_project_role):
    - System admin: all projects
    - Public projects: all authenticated users
    - Private projects: members, or project creator
    """
    all_projects = db.query(Project).all()

    # System admin / qa_manager sees everything
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

    total_tc = 0
    total_pass = 0
    total_fail = 0
    total_block = 0
    total_na = 0
    total_not_started = 0

    project_summaries = []

    for proj in projects:
        count = db.query(TestCase).filter(TestCase.project_id == proj.id, TestCase.deleted_at.is_(None)).count()
        total_tc += count

        # Get latest TestRun for this project
        latest_run = _get_latest_run_for_project(proj.id, db)

        if latest_run:
            # 활성 TC의 결과만 집계 (소프트 삭제된 TC 제외)
            active_tc_ids = set(
                r[0] for r in db.query(TestCase.id).filter(
                    TestCase.project_id == proj.id, TestCase.deleted_at.is_(None)
                ).all()
            )
            results = [
                r for r in db.query(TestResult).filter(
                    TestResult.test_run_id == latest_run.id
                ).all()
                if r.test_case_id in active_tc_ids
            ]
            c = _count_results(results)
            # 결과가 없는 활성 TC도 미수행으로 집계
            tc_with_results = {r.test_case_id for r in results}
            no_result_count = len(active_tc_ids - tc_with_results)
            c["not_started"] += no_result_count
        else:
            c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": count}

        p, f, b, na, ns = c["pass"], c["fail"], c["block"], c["na"], c["not_started"]

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
