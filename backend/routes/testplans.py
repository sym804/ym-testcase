from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import User, Project, TestPlan, TestRun, TestResult, TestResultValue
from schemas import TestPlanCreate, TestPlanUpdate, TestPlanResponse
from auth import check_project_access

router = APIRouter(
    prefix="/api/projects/{project_id}/testplans",
    tags=["testplans"],
)


def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _plan_progress(plan_id: int, db: Session) -> dict:
    """테스트 플랜에 연결된 TestRun들의 결과 합산"""
    runs = db.query(TestRun).filter(TestRun.test_plan_id == plan_id).all()
    if not runs:
        return {"total": 0, "pass": 0, "fail": 0, "block": 0, "na": 0, "ns": 0, "pass_rate": 0.0}

    run_ids = [r.id for r in runs]
    results = (
        db.query(TestResult.result, func.count(TestResult.id))
        .filter(TestResult.test_run_id.in_(run_ids))
        .group_by(TestResult.result)
        .all()
    )
    counts = {r.value: 0 for r in TestResultValue}
    for result_val, cnt in results:
        counts[result_val.value if hasattr(result_val, "value") else result_val] = cnt

    total = sum(counts.values())
    executed = counts.get("PASS", 0) + counts.get("FAIL", 0) + counts.get("BLOCK", 0)
    pass_rate = round(counts.get("PASS", 0) / executed * 100, 1) if executed > 0 else 0.0

    return {
        "total": total,
        "pass": counts.get("PASS", 0),
        "fail": counts.get("FAIL", 0),
        "block": counts.get("BLOCK", 0),
        "na": counts.get("NA", 0),
        "ns": counts.get("NS", 0),
        "pass_rate": pass_rate,
    }


from sqlalchemy import case as sa_case


def _bulk_plan_stats(plan_ids: list[int], db: Session) -> dict[int, tuple[int, dict]]:
    """여러 플랜의 run_count + progress를 2회 SQL로 일괄 조회 (N+1 방지)"""
    if not plan_ids:
        return {}

    # 1) 플랜별 run count — 1회 쿼리
    run_counts_rows = (
        db.query(TestRun.test_plan_id, func.count(TestRun.id))
        .filter(TestRun.test_plan_id.in_(plan_ids))
        .group_by(TestRun.test_plan_id)
        .all()
    )
    run_counts = dict(run_counts_rows)

    # 2) 플랜별 결과 집계 — 1회 쿼리
    progress_rows = (
        db.query(
            TestRun.test_plan_id,
            func.sum(sa_case((TestResult.result == TestResultValue.PASS, 1), else_=0)).label("p"),
            func.sum(sa_case((TestResult.result == TestResultValue.FAIL, 1), else_=0)).label("f"),
            func.sum(sa_case((TestResult.result == TestResultValue.BLOCK, 1), else_=0)).label("b"),
            func.sum(sa_case((TestResult.result == TestResultValue.NA, 1), else_=0)).label("na"),
            func.sum(sa_case((TestResult.result == TestResultValue.NS, 1), else_=0)).label("ns"),
            func.count(TestResult.id).label("total"),
        )
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .filter(TestRun.test_plan_id.in_(plan_ids))
        .group_by(TestRun.test_plan_id)
        .all()
    )

    empty = {"total": 0, "pass": 0, "fail": 0, "block": 0, "na": 0, "ns": 0, "pass_rate": 0.0}
    result: dict[int, tuple[int, dict]] = {}

    progress_map = {}
    for row in progress_rows:
        p, f, b = row.p or 0, row.f or 0, row.b or 0
        executed = p + f + b
        pass_rate = round(p / executed * 100, 1) if executed > 0 else 0.0
        progress_map[row.test_plan_id] = {
            "total": row.total or 0,
            "pass": p, "fail": f, "block": b,
            "na": row.na or 0, "ns": row.ns or 0,
            "pass_rate": pass_rate,
        }

    for pid in plan_ids:
        result[pid] = (run_counts.get(pid, 0), progress_map.get(pid, empty.copy()))

    return result


@router.get("", response_model=List[TestPlanResponse])
def list_test_plans(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    _get_project_or_404(project_id, db)
    plans = (
        db.query(TestPlan)
        .filter(TestPlan.project_id == project_id)
        .order_by(TestPlan.created_at.desc())
        .all()
    )

    # 일괄 조회로 N+1 제거 (플랜 수와 무관하게 SQL 2회)
    stats = _bulk_plan_stats([p.id for p in plans], db)

    result = []
    for p in plans:
        run_count, progress = stats.get(p.id, (0, {"total": 0, "pass": 0, "fail": 0, "block": 0, "na": 0, "ns": 0, "pass_rate": 0.0}))
        r = TestPlanResponse.model_validate(p)
        r.run_count = run_count
        r.progress = progress
        result.append(r)
    return result


@router.post("", response_model=TestPlanResponse, status_code=201)
def create_test_plan(
    project_id: int,
    payload: TestPlanCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    _get_project_or_404(project_id, db)

    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="플랜 이름을 입력해 주세요.")

    plan = TestPlan(
        project_id=project_id,
        name=name,
        milestone=payload.milestone,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_by=current_user.id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    r = TestPlanResponse.model_validate(plan)
    r.run_count = 0
    r.progress = {"total": 0, "pass": 0, "fail": 0, "block": 0, "na": 0, "ns": 0, "pass_rate": 0.0}
    return r


@router.get("/{plan_id}", response_model=TestPlanResponse)
def get_test_plan(
    project_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="테스트 플랜을 찾을 수 없습니다.")

    run_count = db.query(TestRun).filter(TestRun.test_plan_id == plan.id).count()
    progress = _plan_progress(plan.id, db)
    r = TestPlanResponse.model_validate(plan)
    r.run_count = run_count
    r.progress = progress
    return r


@router.put("/{plan_id}", response_model=TestPlanResponse)
def update_test_plan(
    project_id: int,
    plan_id: int,
    payload: TestPlanUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="테스트 플랜을 찾을 수 없습니다.")

    for field in ["name", "milestone", "description", "start_date", "end_date"]:
        val = getattr(payload, field, None)
        if val is not None:
            setattr(plan, field, val)

    db.commit()
    db.refresh(plan)

    run_count = db.query(TestRun).filter(TestRun.test_plan_id == plan.id).count()
    progress = _plan_progress(plan.id, db)
    r = TestPlanResponse.model_validate(plan)
    r.run_count = run_count
    r.progress = progress
    return r


@router.delete("/{plan_id}")
def delete_test_plan(
    project_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("admin")),
):
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="테스트 플랜을 찾을 수 없습니다.")

    # TestRun의 test_plan_id를 null로 해제
    db.query(TestRun).filter(TestRun.test_plan_id == plan_id).update(
        {TestRun.test_plan_id: None}, synchronize_session="fetch"
    )

    db.delete(plan)
    db.commit()
    return {"deleted": plan.name}


@router.get("/{plan_id}/runs")
def list_plan_runs(
    project_id: int,
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """테스트 플랜에 연결된 TestRun 목록"""
    plan = db.query(TestPlan).filter(
        TestPlan.id == plan_id, TestPlan.project_id == project_id
    ).first()
    if not plan:
        raise HTTPException(status_code=404, detail="테스트 플랜을 찾을 수 없습니다.")

    runs = (
        db.query(TestRun)
        .filter(TestRun.test_plan_id == plan_id)
        .order_by(TestRun.created_at.desc())
        .all()
    )

    from schemas import TestRunListResponse
    return [TestRunListResponse.model_validate(r) for r in runs]
