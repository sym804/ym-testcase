from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
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

def version_key(version) -> str:
    """버전 묶음 키. 앞의 v 와 대소문자 · 공백을 무시한다("v1.5" 와 "1.5" 는 하나). 수행 목록 트리와 같은 규칙."""
    return (version or "").strip().lower().lstrip("v")


def _version_filter(version: str):
    """수행의 버전이 version 묶음에 드는지. SQL 에서 같은 규칙으로 정규화한다."""
    return func.ltrim(func.lower(func.trim(func.coalesce(TestRun.version, ""))), "v") == version_key(version)


def _date_bounds(date_from: Optional[str], date_to: Optional[str]):
    """기간 필터의 (시작, 끝) 시각. 없는 쪽은 None. 끝은 그날 23:59:59 까지다.

    ★형식이 틀리면 400 이다. fromisoformat 의 ValueError 가 전역 핸들러까지 올라가 500 이
      됐다. date_to 에 시각까지 보내면("2026-10-01T00:00") 뒤에 붙이는
      T23:59:59 와 겹쳐 역시 깨지므로 날짜만 받는다.
    """
    try:
        start = datetime.fromisoformat(date_from) if date_from else None
        end = datetime.fromisoformat(date_to + "T23:59:59") if date_to else None
    except ValueError:
        raise HTTPException(status_code=400, detail="날짜는 YYYY-MM-DD 형식으로 보내 주세요.")
    return start, end


def _created_at_filters(date_from: Optional[str], date_to: Optional[str]) -> list:
    """수행 생성 시각으로 거르는 조건 목록."""
    start, end = _date_bounds(date_from, date_to)
    out = []
    if start is not None:
        out.append(TestRun.created_at >= start)
    if end is not None:
        out.append(TestRun.created_at <= end)
    return out


def _latest_run_subquery(project_id: int, db: Session, date_from: str = None, date_to: str = None,
                         version: str = None):
    """TC별로 마지막으로 판정된 런의 test_run_id를 구하는 서브쿼리.

    version 을 주면 그 버전 묶음의 수행만 본다(09-30). 예전에는 "전체" 가 프로젝트의 모든
    수행을 섞어 v1.4 결과가 v1.5 현황에 끼었다.

    NS 는 판정이 아니라서 뺀다(SYM-131). 넣으면 새 수행을 만들기만 해도 그 수행이 담은 TC 가
    전부 최신 NS 가 되어 앞 수행의 PASS/FAIL 이 미수행으로 바뀐다(실측 stockradar: PASS 519 -> 0).
    """
    run_filter = [TestRun.project_id == project_id, TestResult.result != TestResultValue.NS,
                  *_created_at_filters(date_from, date_to)]
    if version:
        run_filter.append(_version_filter(version))

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


def _active_counts_query(db: Session, project_id: int):
    """결과 카운트 쿼리의 공통 골격. 분자는 언제나 이 프로젝트의 활성 TC 로 좁힌다.

    ★두 가지를 한 자리에서 건다. 분모(total)는 활성 TC 인데 분자가 결과 행 전체면
      지운 TC 의 결과가 남아 합격률이 부풀려진다(실측 36.4% -> 40.0%, 많이 지우면
      pass 가 total 을 넘는다). 그리고 run_id 만 보고 프로젝트를 안 보면 남의
      프로젝트 런 집계가 그대로 나온다(실측 total=0 인데 pass=504).
      run_id 분기에만 필터가 있고 전체 모드에 없어서 갈라졌던 자리다. 다시
      갈라지지 않도록 두 분기가 이 함수를 함께 쓴다.
    """
    cases = _result_count_cases()
    return (
        db.query(
            cases["pass"].label("pass_count"),
            cases["fail"].label("fail_count"),
            cases["block"].label("block_count"),
            cases["na"].label("na_count"),
        )
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
        )
    )


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


# ── Summary ───────────────────────────────────────────────────────────────────

def _run_tc_ids(run_id: int, db: Session):
    """런이 담고 있는 TC id 서브쿼리.

    시트를 골라 만든 런은 프로젝트 TC 의 일부만 담는다. 총계를 프로젝트 전체로
    잡으면 그 런을 전부 수행해도 진행률이 100%% 에 닿지 않는다(실측: 4/4 를 PASS
    했는데 36.4%%). 런의 결과 행이 곧 그 런의 범위이므로 그것으로 좁힌다.
    """
    return db.query(TestResult.test_case_id).filter(TestResult.test_run_id == run_id).subquery()


@router.get("/summary")
def dashboard_summary(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    total_q = db.query(TestCase).filter(
        TestCase.project_id == project_id,
        TestCase.deleted_at.is_(None),
    )
    if run_id:
        total_q = total_q.filter(TestCase.id.in_(db.query(_run_tc_ids(run_id, db).c.test_case_id)))
    total = total_q.count()

    if run_id:
        row = (
            _active_counts_query(db, project_id)
            .filter(TestResult.test_run_id == run_id)
            .first()
        )
        if row and (row.pass_count or row.fail_count or row.block_count or row.na_count):
            c = _counts_from_row(row, total)
        else:
            c = {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": total}
        return {"total": total, **c, **_rates(c, total)}

    # 전체 모드: SQL 집계로 TC별 마지막 판정(NS 제외) 카운트
    latest = _latest_run_subquery(project_id, db, date_from, date_to, version)
    row = (
        _active_counts_query(db, project_id)
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
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    # 집계할 TC 가 없어 일찍 돌아가도 형식이 틀린 날짜는 같은 400 으로 알린다.
    _date_bounds(date_from, date_to)
    # TC priority별 총 건수
    priority_totals_q = (
        db.query(TestCase.priority, func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestCase.priority.isnot(None),
        )
    )
    if run_id:
        priority_totals_q = priority_totals_q.filter(
            TestCase.id.in_(db.query(_run_tc_ids(run_id, db).c.test_case_id))
        )
    priority_totals = dict(priority_totals_q.group_by(TestCase.priority).all())
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
        latest = _latest_run_subquery(project_id, db, date_from, date_to, version)
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
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    # 집계할 TC 가 없어 일찍 돌아가도 형식이 틀린 날짜는 같은 400 으로 알린다.
    _date_bounds(date_from, date_to)
    category_totals_q = (
        db.query(TestCase.category, func.count(TestCase.id))
        .filter(
            TestCase.project_id == project_id,
            TestCase.deleted_at.is_(None),
            TestCase.category.isnot(None),
        )
    )
    if run_id:
        category_totals_q = category_totals_q.filter(
            TestCase.id.in_(db.query(_run_tc_ids(run_id, db).c.test_case_id))
        )
    category_totals = dict(category_totals_q.group_by(TestCase.category).all())
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
        latest = _latest_run_subquery(project_id, db, date_from, date_to, version)
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
    run_name: Optional[str] = Query(None, description="회차를 묶을 수행 이름. 없으면 가장 최근 수행의 이름"),
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """같은 이름의 수행을 회차(R1, R2...) 순으로 돌려준다. 라운드별 비교와 Pass/Fail 추이가 쓴다.

    ★예전에는 프로젝트의 모든 수행을 회차 번호로만 묶고 번호마다 가장 최근 것 하나를
      골랐다. 이름이 다른 테스트가 한 줄로 이어져(계정·세션 정책 R1 다음이 Full 테스트
      R2 같은 식) 추이로 읽을 수 없었고, 같은 R1 끼리 밀린 수행은 어디에도 안 나왔다.
      리포트의 비교 대상과 같은 규칙으로 같은 이름끼리만 묶는다.
    ★합격률은 리포트·요약 카드와 같은 분모(PASS+FAIL+BLOCK)다. 화면이 N/A 까지 넣어
      다시 계산하던 것을 없앴다. 실행이 0건이면 0% 가 아니라 null 이다. 진행 중인
      회차가 0% 로 찍혀 폭락처럼 보였다.
    """
    run_q = db.query(TestRun).filter(TestRun.project_id == project_id,
                                     *_created_at_filters(date_from, date_to))
    if version:
        run_q = run_q.filter(_version_filter(version))

    if not run_name:
        latest = run_q.order_by(TestRun.created_at.desc(), TestRun.id.desc()).first()
        if latest is None:
            return []
        run_name = latest.name
    runs = (
        run_q.filter(TestRun.name == run_name)
        .order_by(TestRun.round, TestRun.created_at.desc(), TestRun.id.desc())
        .all()
    )

    # 같은 이름에 같은 회차가 둘이면(복제 등) 가장 최근 것을 쓴다
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
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .filter(TestResult.test_run_id.in_(run_ids), TestCase.deleted_at.is_(None))
        .group_by(TestResult.test_run_id)
        .all()
    )

    # 라운드마다 담은 범위가 다를 수 있다. 시트를 골라 만든 런은 프로젝트 전체가
    # 아니라 그 런의 결과 행 수가 분모다.
    run_totals = dict(
        db.query(TestResult.test_run_id, func.count(TestResult.id))
        .join(TestCase, TestCase.id == TestResult.test_case_id)
        .filter(TestResult.test_run_id.in_(run_ids), TestCase.deleted_at.is_(None))
        .group_by(TestResult.test_run_id)
        .all()
    )

    counts_by_run = {}
    for row in rows:
        c = _counts_from_row(row, run_totals.get(row.test_run_id, 0))
        counts_by_run[row.test_run_id] = c

    result = []
    for round_num in sorted(seen_rounds.keys()):
        run = seen_rounds[round_num]
        # ★결과 행이 없는 런은 담은 것이 없다는 뜻이다. 프로젝트 전체 TC 로 되돌리면
        #   빈 런이 "전부 미실행" 으로 보인다.
        run_total = run_totals.get(run.id, 0)
        c = counts_by_run.get(run.id, {"pass": 0, "fail": 0, "block": 0, "na": 0, "not_started": run_total})

        executed = c["pass"] + c["fail"] + c["block"]
        result.append({
            "round": round_num,
            "run_id": run.id,
            "name": run.name,
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "total": run_total,
            **c,
            "executed": executed,
            "pass_rate": round(c["pass"] / executed * 100, 1) if executed > 0 else None,
            "fail_rate": round(c["fail"] / executed * 100, 1) if executed > 0 else None,
        })

    return result


# ── Assignee Summary (deprecated - assignee 필드 v1.2.0에서 제거됨) ─────────

@router.get("/assignee")
def assignee_summary(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """assignee 필드가 v1.2.0에서 제거되어 빈 배열 반환.

    화면은 v1.5.4.0 에서 이 표를 걷어냈다(늘 비어 있어 "데이터가 없나" 로 읽혔다).
    외부에서 이 엔드포인트를 부르는 쪽이 있을 수 있어 라우트만 남긴다.
    """
    return []


@router.get("/heatmap")
def get_heatmap(
    project_id: int,
    run_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
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

    # 전체 모드: TC별 마지막 판정(NS 제외) 기준 FAIL만 집계
    latest = _latest_run_subquery(project_id, db, date_from, date_to, version)
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


#: 안정성에서 실행으로 세는 결과. NA · NS 는 수행하지 않은 것이라 뺀다.
_EXECUTED = (TestResultValue.PASS, TestResultValue.FAIL, TestResultValue.BLOCK)


@router.get("/stability")
def tc_stability(
    project_id: int,
    date_from: Optional[str] = Query(None, description="시작일 (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="종료일 (YYYY-MM-DD)"),
    version: Optional[str] = Query(None, description="버전 묶음(앞의 v · 대소문자 무시). 없으면 전체"),
    min_runs: int = Query(2, ge=2, le=50, description="이만큼 실행된 TC 만 본다"),
    limit: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """TC 별 실행 이력으로 본 안정성.

    수행(회차)마다 쌓인 결과를 시간 순으로 늘어놓고, PASS 와 그 밖(FAIL · BLOCK) 사이를 오간
    횟수를 센다. 오간 적이 있으면 불안정 TC 다(flaky 후보, 또는 고쳐졌다 다시 깨진 것).
    매번 실패한 TC 는 따로 센다. test.fail 로 고정한 결함 재현이 여기에 든다.
    재시도는 한 수행 안의 일이라 여기서 보이지 않는다. 회차 사이의 변동만 본다.
    """
    run_filter = [TestRun.project_id == project_id, *_created_at_filters(date_from, date_to)]
    if version:
        run_filter.append(_version_filter(version))

    rows = (
        db.query(TestResult.test_case_id, TestResult.result, TestRun.name, TestRun.round)
        .join(TestRun, TestResult.test_run_id == TestRun.id)
        .join(TestCase, TestResult.test_case_id == TestCase.id)
        .filter(*run_filter, TestCase.deleted_at.is_(None), TestResult.result.in_(_EXECUTED))
        .order_by(TestResult.test_case_id, TestRun.created_at, TestRun.id)
        .all()
    )
    history: dict[int, list] = {}
    for tc_pk, result, run_name, run_round in rows:
        history.setdefault(tc_pk, []).append((result, run_name, run_round))

    analyzed = unstable_n = always_fail_n = 0
    unstable = []
    for tc_pk, seq in history.items():
        if len(seq) < min_runs:
            continue
        analyzed += 1
        passed = [r == TestResultValue.PASS for r, _, _ in seq]
        flips = sum(1 for a, b in zip(passed, passed[1:]) if a != b)
        fails = sum(1 for r, _, _ in seq if r == TestResultValue.FAIL)
        if fails == len(seq):
            always_fail_n += 1
        if flips == 0:
            continue
        unstable_n += 1
        last = seq[-1]
        unstable.append({
            "test_case_id": tc_pk,
            "executed": len(seq),
            "fail": fails,
            "block": sum(1 for r, _, _ in seq if r == TestResultValue.BLOCK),
            "fail_rate": round(fails / len(seq) * 100, 1),
            "flips": flips,
            "flip_rate": round(flips / (len(seq) - 1) * 100, 1),
            # 최근 10회. 왼쪽이 오래된 것이다
            "recent": [r.value for r, _, _ in seq[-10:]],
            "last_run": f"{last[1]} R{last[2]}",
        })

    unstable.sort(key=lambda x: (-x["flip_rate"], -x["flips"], -x["executed"], x["test_case_id"]))
    unstable = unstable[:limit]
    tcs = {
        tc.id: tc for tc in db.query(TestCase.id, TestCase.tc_id, TestCase.category, TestCase.sheet_name)
        .filter(TestCase.id.in_([u["test_case_id"] for u in unstable])).all()
    } if unstable else {}
    for u in unstable:
        tc = tcs.get(u["test_case_id"])
        u["tc_id"] = tc.tc_id if tc else ""
        u["category"] = (tc.category or "") if tc else ""
        u["sheet_name"] = tc.sheet_name if tc else ""

    return {
        "min_runs": min_runs,
        "analyzed": analyzed,
        "unstable_count": unstable_n,
        "always_fail_count": always_fail_n,
        "unstable": unstable,
    }
