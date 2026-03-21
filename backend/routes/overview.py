from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models import User, UserRole, Project, ProjectMember, TestCase, TestRun, TestResult
from auth import get_current_user

router = APIRouter(
    prefix="/api/dashboard",
    tags=["overview"],
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

    project_ids = [p.id for p in projects]

    # 1) 프로젝트별 활성 TC 수를 한 번에 조회
    from sqlalchemy import func
    tc_counts_rows = (
        db.query(TestCase.project_id, func.count(TestCase.id))
        .filter(TestCase.project_id.in_(project_ids), TestCase.deleted_at.is_(None))
        .group_by(TestCase.project_id)
        .all()
    ) if project_ids else []
    tc_counts = dict(tc_counts_rows)

    # 2) 프로젝트별 활성 TC ID 세트
    active_tc_rows = (
        db.query(TestCase.project_id, TestCase.id)
        .filter(TestCase.project_id.in_(project_ids), TestCase.deleted_at.is_(None))
        .all()
    ) if project_ids else []
    active_tc_by_project: dict[int, set] = {}
    for pid, tid in active_tc_rows:
        active_tc_by_project.setdefault(pid, set()).add(tid)

    # 3) 프로젝트별 최신 TestRun 한 번에 조회
    latest_runs_rows = (
        db.query(TestRun)
        .filter(TestRun.project_id.in_(project_ids))
        .order_by(TestRun.project_id, TestRun.created_at.desc())
        .all()
    ) if project_ids else []
    latest_run_by_project: dict[int, TestRun] = {}
    for run in latest_runs_rows:
        if run.project_id not in latest_run_by_project:
            latest_run_by_project[run.project_id] = run

    # 4) 최신 런들의 결과를 한 번에 조회
    latest_run_ids = [run.id for run in latest_run_by_project.values()]
    all_results = (
        db.query(TestResult)
        .filter(TestResult.test_run_id.in_(latest_run_ids))
        .all()
    ) if latest_run_ids else []
    results_by_run: dict[int, list] = {}
    for r in all_results:
        results_by_run.setdefault(r.test_run_id, []).append(r)

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

        latest_run = latest_run_by_project.get(proj.id)

        if latest_run:
            active_ids = active_tc_by_project.get(proj.id, set())
            run_results = [r for r in results_by_run.get(latest_run.id, []) if r.test_case_id in active_ids]
            c = _count_results(run_results)
            tc_with_results = {r.test_case_id for r in run_results}
            no_result_count = len(active_ids - tc_with_results)
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
