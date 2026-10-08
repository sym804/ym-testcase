import io
import re
import os
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, load_only
from sqlalchemy import func, case
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import logging

from database import get_db
from models import (
    User, Project, TestRun, TestResult, TestCase, TestResultValue,
    ISSUE_GROUP_ORDER, issue_group,
)
from services.excel_safe import safe_cell
from services.issue_key import find_issue_refs
from services.sheet_order import leaf_sheet_order, sort_results_for_export
from auth import get_current_user, check_project_access

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/reports",
    tags=["reports"],
)



# models.now_kst 와 같은 고정 오프셋. 한국은 서머타임이 없고, zoneinfo 는 시간대 DB(tzdata)가
# 없는 환경에서 실패한다.
KST = timezone(timedelta(hours=9))


def report_now(now=None):
    """리포트에 찍는 현재 시각. 서버 시간대(Vercel 함수는 UTC)와 무관하게 KST 다.

    DB 의 시각(models.now_kst)과 같은 형태로 맞추려고 시간대 정보를 뗀다.
    """
    base = now or datetime.now(tz=KST)
    return base.astimezone(KST).replace(tzinfo=None)

def _get_project_or_404(project_id: int, db: Session) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


def _get_run_or_404(project_id: int, test_run_id: int, db: Session) -> TestRun:
    run = db.query(TestRun).filter(
        TestRun.id == test_run_id, TestRun.project_id == project_id
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Test run not found")
    return run


def _summary_sql(run_id: int, db: Session) -> dict:
    """SQL 집계로 summary 생성 (Python 루프 대신).

    ★리포트는 그때의 수행 기록이다. 런에 편입된 뒤 지워진 TC 의 결과도 그대로
      센다. 지금 상태를 보는 대시보드와 기준이 다른 것은 의도다. 두 화면의
      질문이 다르기 때문이다("그때 몇 건을 수행했나" 대 "지금 몇 건이 남았나").
      이 기록이 7일 뒤 purge 로 사라지지 않도록 `_purge_old_deleted_testcases`
      가 결과 행이 있는 TC 를 건너뛴다.
    """
    row = db.query(
        func.count(TestResult.id).label("total"),
        func.sum(case((TestResult.result == TestResultValue.PASS, 1), else_=0)).label("passed"),
        func.sum(case((TestResult.result == TestResultValue.FAIL, 1), else_=0)).label("failed"),
        func.sum(case((TestResult.result == TestResultValue.BLOCK, 1), else_=0)).label("blocked"),
        func.sum(case((TestResult.result == TestResultValue.NA, 1), else_=0)).label("na"),
        func.sum(case((TestResult.result == TestResultValue.NS, 1), else_=0)).label("ns"),
    ).filter(TestResult.test_run_id == run_id).first()

    total = row.total or 0
    passed = row.passed or 0
    failed = row.failed or 0
    blocked = row.blocked or 0
    na = row.na or 0
    ns = row.ns or 0
    executed = passed + failed + blocked
    pass_rate = round(passed / executed * 100, 1) if executed > 0 else 0.0

    return {
        "total": total, "executed": executed, "passed": passed, "failed": failed,
        "blocked": blocked, "na": na, "ns": ns, "pass_rate": pass_rate,
    }


def _category_summary_sql(run_id: int, db: Session) -> list:
    """SQL 집계로 카테고리별 통계 생성."""
    rows = (
        db.query(
            TestCase.category,
            func.count(TestResult.id).label("total"),
            func.sum(case((TestResult.result == TestResultValue.PASS, 1), else_=0)).label("passed"),
            func.sum(case((TestResult.result == TestResultValue.FAIL, 1), else_=0)).label("failed"),
            func.sum(case((TestResult.result == TestResultValue.BLOCK, 1), else_=0)).label("blocked"),
            func.sum(case((TestResult.result == TestResultValue.NA, 1), else_=0)).label("na"),
            func.sum(case((TestResult.result == TestResultValue.NS, 1), else_=0)).label("ns"),
        )
        .join(TestResult, TestResult.test_case_id == TestCase.id)
        .filter(TestResult.test_run_id == run_id)
        .group_by(TestCase.category)
        .all()
    )
    # NULL 과 빈 문자열을 한 줄(None)로 합친다. 따로 두면 같은 이름의 행이 두 번 나온다.
    # ★이름을 여기서 정하지 않는다. 예전에는 "Uncategorized" 로 박아서 요약 표는
    #   "Uncategorized", 실패·차단 목록은 "-" 로 같은 TC 가 다르게 불렸다.
    #   JSON 은 null 로 보내 화면이 번역하고, PDF/엑셀은 REPORT_TEXT 의 unset_category 를 쓴다.
    merged: dict = {}
    for r in rows:
        name = (r.category or "").strip() or None
        m = merged.setdefault(name, {"category": name, "total": 0, "passed": 0, "failed": 0,
                                     "blocked": 0, "na": 0, "not_started": 0})
        m["total"] += r.total or 0
        m["passed"] += r.passed or 0
        m["failed"] += r.failed or 0
        m["blocked"] += r.blocked or 0
        m["na"] += r.na or 0
        m["not_started"] += r.ns or 0
    return list(merged.values())


# 우선순위 값은 자유 입력이라 프로젝트마다 어휘가 다르다(실 DB: High/Medium/Low,
# 매우 높음/높음/중간/낮음, 핵심/중요/보통). 아는 값은 높은 것부터, 모르는 값은
# 그 뒤에 이름순, 비어 있으면 맨 뒤다.
_PRIORITY_RANK = {
    name.lower(): rank
    for rank, names in enumerate([
        ["critical", "blocker", "매우 높음", "핵심", "p0"],
        ["high", "높음", "중요", "p1"],
        ["medium", "중간", "보통", "p2"],
        ["low", "낮음", "p3"],
        ["trivial", "매우 낮음", "p4"],
    ])
    for name in names
}
# 우선순위·분류를 비운 TC 의 이름은 REPORT_TEXT 의 unset_priority · unset_category 다.
# JSON 에는 null 로 보내고 화면이 번역한다.


def priority_sort_key(priority) -> tuple:
    if priority is None or str(priority).strip() == "":
        return (2, 0, "")
    text = str(priority).strip()
    rank = _PRIORITY_RANK.get(text.lower())
    if rank is None:
        return (1, 0, text)
    return (0, rank, "")


def _rate(passed: int, executed: int):
    """합격률. 분모는 수행분(pass+fail+block)이다(SYM-57). 수행이 없으면 None."""
    return round(passed / executed * 100, 1) if executed > 0 else None


def _issue_items(run: TestRun, db: Session) -> list:
    """FAIL 과 BLOCK 결과. 우선순위 높은 것부터, 같으면 수행 엑셀과 같은 차례다.

    ★BLOCK 을 빼지 않는다. 예전에는 FAIL 만 모아서 BLOCK 만 있는 수행이
      "실패 항목이 없습니다" 로 나왔고, 막힌 사유와 이슈 링크가 웹과 PDF 어디에도
      안 실렸다(엑셀 Results 시트에만 있었다).
    """
    results = (
        db.query(TestResult)
        .options(
            joinedload(TestResult.test_case).load_only(
                TestCase.no, TestCase.tc_id, TestCase.category, TestCase.priority,
                TestCase.depth1, TestCase.depth2, TestCase.test_steps,
                TestCase.expected_result, TestCase.sheet_name,
            ),
            joinedload(TestResult.executor).load_only(User.display_name),
        )
        .filter(
            TestResult.test_run_id == run.id,
            TestResult.result.in_([TestResultValue.FAIL, TestResultValue.BLOCK]),
        )
        .all()
    )
    results = sort_results_for_export(results, leaf_sheet_order(run.project_id, db))
    # sorted 는 안정 정렬이라 우선순위가 같으면 위의 차례가 유지된다
    results = sorted(results, key=lambda r: priority_sort_key(r.test_case.priority))
    return [
        {
            "tc_id": r.test_case.tc_id,
            "result": r.result.value if hasattr(r.result, "value") else r.result,
            # 빈 문자열과 공백만 있는 값은 None 이다. 요약 표(_category_summary_sql)와 같은 규칙.
            "priority": (r.test_case.priority or "").strip() or None,
            "category": (r.test_case.category or "").strip() or None,
            "depth1": r.test_case.depth1,
            "depth2": r.test_case.depth2,
            "test_steps": r.test_case.test_steps,
            "expected_result": r.test_case.expected_result,
            "actual_result": r.actual_result,
            "issue_link": r.issue_link,
            "executed_by": r.executor.display_name if r.executor else None,
        }
        for r in results
    ]


def _priority_summary_sql(run_id: int, db: Session) -> list:
    """우선순위별 결과. 리포트 규약대로 이 런의 결과 행을 센다(지워진 TC 포함).

    대시보드의 `/priority` 는 지금 남은 TC 만 세므로 그대로 쓰지 않는다.
    """
    rows = (
        db.query(
            TestCase.priority,
            func.count(TestResult.id).label("total"),
            func.sum(case((TestResult.result == TestResultValue.PASS, 1), else_=0)).label("passed"),
            func.sum(case((TestResult.result == TestResultValue.FAIL, 1), else_=0)).label("failed"),
            func.sum(case((TestResult.result == TestResultValue.BLOCK, 1), else_=0)).label("blocked"),
            func.sum(case((TestResult.result == TestResultValue.NA, 1), else_=0)).label("na"),
            func.sum(case((TestResult.result == TestResultValue.NS, 1), else_=0)).label("ns"),
        )
        .join(TestResult, TestResult.test_case_id == TestCase.id)
        .filter(TestResult.test_run_id == run_id)
        .group_by(TestCase.priority)
        .all()
    )
    # 공백만 다른 값과 NULL 을 한 줄로 합친다
    merged: dict = {}
    for r in rows:
        text = str(r.priority).strip() if r.priority is not None else ""
        key = text or None
        m = merged.setdefault(key, {"total": 0, "passed": 0, "failed": 0, "blocked": 0, "na": 0, "ns": 0})
        for f in m:
            m[f] += getattr(r, f) or 0
    out = []
    for key in sorted(merged, key=priority_sort_key):
        m = merged[key]
        executed = m["passed"] + m["failed"] + m["blocked"]
        out.append({
            "priority": key,
            "total": m["total"], "passed": m["passed"], "failed": m["failed"],
            "blocked": m["blocked"], "na": m["na"], "not_started": m["ns"],
            "pass_rate": _rate(m["passed"], executed),
        })
    return out


def _compare_target(run: TestRun, db: Session):
    """비교 대상 수행과 정한 방식("manual" / "auto")을 돌려준다. 없으면 (None, None).

    1. 수행에 저장한 비교 대상(compare_run_id)이 있으면 그것.
    2. 없으면 같은 이름의 이전 회차 가운데 회차가 가장 큰 것. R2 면 R1 이다.
    3. 그것도 없으면(R1 이거나 이름이 다르면) 비교하지 않는다.

    ★예전에는 "바로 전에 만든 수행" 을 이름과 상관없이 골랐다. 그래서 계정·세션
      정책 R1 이 관계없는 Full 테스트와 비교되어 겹치는 TC 0건인 결과가 실렸다.
      비교 대상을 모를 때는 싣지 않는 편이 낫다. 필요하면 사람이 고른다.
    """
    if run.compare_run_id:
        target = db.query(TestRun).filter(
            TestRun.id == run.compare_run_id, TestRun.project_id == run.project_id,
        ).first()
        if target is not None:
            return target, "manual"
    target = (
        db.query(TestRun)
        .filter(
            TestRun.project_id == run.project_id,
            TestRun.id != run.id,
            TestRun.name == run.name,
            TestRun.round < run.round,
        )
        .order_by(TestRun.round.desc(), TestRun.created_at.desc(), TestRun.id.desc())
        .first()
    )
    return (target, "auto") if target is not None else (None, None)


def _comparison(run: TestRun, db: Session):
    """비교 대상 런 대비 변화(대상은 _compare_target). 판정 기준은 수행 비교 화면(CompareView)과 같다.

    ★퇴보는 PASS -> FAIL, 개선은 FAIL -> PASS 다. 수행 비교 화면과 같은 판정이라
      여기서만 변경하면 같은 두 런을 두 화면이 다른 숫자로 보여 준다.
    ★"변경" 은 두 런에서 모두 수행한(NS 가 아닌) TC 만 센다. 비교 화면과 다른 점이다.
      직전 런이 진행 중이면 대부분 NS 라서, 그대로 세면 NS -> PASS 가 전부 변경으로
      잡힌다(실측: run 25 의 변경 8건이 모두 NS -> PASS 였다).
    """
    prev, mode = _compare_target(run, db)
    if prev is None:
        return None

    def result_map(run_id):
        rows = (
            db.query(TestResult.test_case_id, TestResult.result, TestCase.tc_id, TestCase.priority, TestCase.category)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .filter(TestResult.test_run_id == run_id)
            .all()
        )
        return {
            r.test_case_id: (r.result.value if hasattr(r.result, "value") else r.result, r.tc_id, r.priority, r.category)
            for r in rows
        }

    # 연관 이슈 키. 변경된 TC 옆에 어느 이슈인지 보이도록 한다(이 수행에 등록한 이슈 기준).
    issues_of: dict = {}
    for issue in run.issues:
        for tc_id in issue.tc_ids:
            issues_of.setdefault(tc_id, []).append(issue.issue_key or issue.url)

    before, after = result_map(prev.id), result_map(run.id)
    common = [
        tid for tid in after
        if tid in before and before[tid][0] != "NS" and after[tid][0] != "NS"
    ]
    changed, regressions, fixed, still, others = 0, [], [], [], []
    prev_fail = {"total": 0, "fixed": 0, "still": 0, "other": 0}
    for tid in common:
        old = before[tid][0]
        new, tc_id, priority, category = after[tid]
        item = {"tc_id": tc_id, "priority": priority, "category": category, "before": old, "after": new,
                "issue_keys": issues_of.get(tc_id, [])}
        # ★이전 수행의 FAIL 이 이번에 어떻게 됐는지 따로 센다. 변경만 세면 "FAIL 8건 중 7건
        #   고침" 에서 남은 1건(FAIL 그대로)이 어디에도 안 보인다(09-30 사용자 지적).
        if old == "FAIL":
            prev_fail["total"] += 1
            if new == "PASS":
                prev_fail["fixed"] += 1
            elif new == "FAIL":
                prev_fail["still"] += 1
            else:
                prev_fail["other"] += 1
        if old == new:
            if old == "FAIL":
                still.append({**item, "kind": "still"})
            continue
        changed += 1
        if old == "PASS" and new == "FAIL":
            regressions.append({**item, "kind": "regression"})
        elif old == "FAIL" and new == "PASS":
            fixed.append({**item, "kind": "fixed"})
        else:
            others.append({**item, "kind": "other"})

    def order(items):
        return sorted(items, key=lambda x: (priority_sort_key(x["priority"]), x["tc_id"] or ""))

    return {
        "previous_run": {"id": prev.id, "name": prev.name, "round": prev.round},
        "mode": mode,
        "common": len(common),
        "changed": changed,
        "regressions": order(regressions),
        "fixed": order(fixed),
        "prev_fail": prev_fail,
        # 표에 싣는 차례: 퇴보 -> 미수정(FAIL 그대로) -> 개선 -> 그 밖의 변경. 남은 위험부터.
        "changes": order(regressions) + order(still) + order(fixed) + order(others),
    }


def _executors(run_id: int, db: Session) -> dict:
    """수행자별 건수와 기록된 소요 시간 합. 미수행(NS) 행은 세지 않는다.

    결과 행은 런을 만들 때 NS 로 미리 생기고 executed_by 가 채워지므로, NS 까지
    세면 런을 만든 사람이 전부 수행한 것처럼 나온다.
    """
    rows = (
        db.query(User.display_name, func.count(TestResult.id), func.sum(TestResult.duration_sec))
        .join(User, TestResult.executed_by == User.id)
        .filter(TestResult.test_run_id == run_id, TestResult.result != TestResultValue.NS)
        .group_by(User.id, User.display_name)
        .order_by(func.count(TestResult.id).desc(), User.display_name)
        .all()
    )
    total_sec = sum((r[2] or 0) for r in rows)
    return {
        # count 는 JSON 호환으로 남긴다. 화면·PDF·엑셀은 이름만 보여 준다.
        "executors": [{"name": r[0], "count": r[1]} for r in rows],
        "total_duration_sec": round(total_sec, 1) if total_sec else None,
    }


def _related_issues(items: list) -> list:
    """이슈 링크를 항목 차례대로 중복 없이. set 을 거치면 재시작마다 순서가 변경된다."""
    return list(dict.fromkeys(i["issue_link"] for i in items if i.get("issue_link")))


def _run_issues(run: TestRun, db: Session) -> list:
    """수행에 등록한 이슈. 묶음(미처리 -> 신규 -> 미확인 -> 처리 완료) 차례로, 묶음 안은 넣은 차례.

    tcs_all_pass 는 연관 TC 가 이번 수행에서 전부 PASS 인지다. 미확인 이슈의 "해결 후보"
    표시에만 쓴다. TC 통과가 곧 해결는 아니라서 판정을 자동으로 변경하지 않는다.
    """
    result_of: dict = {}
    for tc_id, result in (
        db.query(TestCase.tc_id, TestResult.result)
        .join(TestResult, TestResult.test_case_id == TestCase.id)
        .filter(TestResult.test_run_id == run.id)
    ):
        result_of[tc_id] = result.value if hasattr(result, "value") else result

    def all_pass(tc_ids):
        if not tc_ids:
            return None
        return all(result_of.get(t) == "PASS" for t in tc_ids)

    rows = [
        {
            "id": i.id,
            "issue_key": i.issue_key,
            "title": i.title,
            "url": i.url,
            "status": i.status,
            "note": i.note,
            "tc_ids": i.tc_ids,
            "origin_run_id": i.origin_run_id,
            "origin_round": i.origin_round,
            # 발견 수행이 지워졌으면 None. 회차 숫자(origin_round)는 남는다.
            "origin_run_name": i.origin_run.name if i.origin_run is not None else None,
            "verdict": i.verdict,
            "group": issue_group(i.origin_round, i.verdict),
            "tcs_all_pass": all_pass(i.tc_ids),
        }
        for i in run.issues
    ]
    order = {g: n for n, g in enumerate(ISSUE_GROUP_ORDER)}
    rows.sort(key=lambda r: (order[r["group"]], r["id"]))
    return rows


def _issue_summary(issues: list) -> dict:
    """묶음별 건수. 리포트 이슈 섹션의 요약 줄이다.

    unverified 는 미해결 가운데 아직 확인하지 않은 수다. 0 이면 이전 회차 이슈를 다 봤다는 뜻.
    """
    counts = {g: 0 for g in ISSUE_GROUP_ORDER}
    counts["unverified"] = 0
    for i in issues:
        counts[i["group"]] += 1
        if _is_unverified(i):
            counts["unverified"] += 1
    return counts


def _issue_summary_text(issues: list, T: dict) -> str:
    c = _issue_summary(issues)
    text = T["issue_summary"].format(**c)
    if c["unverified"]:
        text += T["issue_summary_unverified"].format(**c)
    return text


def _issue_candidates(run: TestRun, registered: list, db: Session) -> list:
    """결과 칸 issue_link 에 적혔지만 이슈 목록에 없는 이슈. 화면이 "추가 후보" 로 보여 준다.

    예전에는 이 칸을 모아 별도 섹션(연관 이슈)으로 실었다. 목록을 하나로 합치면서
    섹션은 없애고, 등록을 돕는 후보로만 쓴다. PDF·엑셀에는 싣지 않는다.
    결과가 무엇이든(PASS 포함) 칸에 적힌 것은 다 본다.
    """
    keys = {i["issue_key"] for i in registered if i["issue_key"]}
    urls = {i["url"] for i in registered}
    rows = (
        db.query(TestResult)
        .options(joinedload(TestResult.test_case).load_only(TestCase.no, TestCase.tc_id, TestCase.sheet_name))
        .filter(TestResult.test_run_id == run.id, TestResult.issue_link.isnot(None), TestResult.issue_link != "")
        .all()
    )
    rows = sort_results_for_export(rows, leaf_sheet_order(run.project_id, db))
    found: dict = {}
    for r in rows:
        for key, url in find_issue_refs(r.issue_link):
            if (key and key in keys) or (url and url in urls):
                continue
            c = found.setdefault(key or url, {"issue_key": key, "url": url, "tc_ids": []})
            if url and not c["url"]:
                c["url"] = url
            if r.test_case.tc_id not in c["tc_ids"]:
                c["tc_ids"].append(r.test_case.tc_id)
    return list(found.values())


def _build_report_data(run: TestRun, db: Session) -> dict:
    """SQL 집계 기반 리포트 데이터 생성 (전체 ORM 로드 없음)."""
    summary = _summary_sql(run.id, db)
    categories = _category_summary_sql(run.id, db)
    for c in categories:
        c["pass_rate"] = _rate(c["passed"], c["passed"] + c["failed"] + c["blocked"])
    items = _issue_items(run, db)

    return {
        "run": {
            "id": run.id,
            "name": run.name,
            "version": run.version,
            "environment": run.environment,
            "round": run.round,
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "compare_run_id": run.compare_run_id,
        },
        "summary": summary,
        "categories": categories,
        "priorities": _priority_summary_sql(run.id, db),
        "issue_items": items,
        "related_issues": _related_issues(items),
        "run_issues": _run_issues(run, db),
        "comparison": _comparison(run, db),
        **_executors(run.id, db),
    }


def _safe_name(text: str) -> str:
    """Windows 에서 못 쓰는 글자는 밑줄로 변경한다."""
    bad = set(chr(92) + '/:*?"<>|')
    return "".join("_" if ch in bad or ord(ch) < 32 else ch for ch in text).strip()


def _run_slug(project_name: str, run: TestRun) -> str:
    """파일 이름에 넣을 수행 이름. "Starfort 1.5 계정 · 세션 정책 테스트" -> "계정·세션정책".

    프로젝트 이름과 버전은 파일 이름의 다른 자리에 이미 있으니 빼고, 꼬리의 "테스트"/"Test" 도
    빼며(파일 이름에 Test_Report 가 붙는다), 남은 글자는 공백 없이 붙인다(09-30 사용자 형식).
    """
    from routes.dashboard import version_key

    name = (run.name or "").strip()
    proj = (project_name or "").strip()
    if proj and name.lower().startswith(proj.lower()):
        name = name[len(proj):].strip()
    if run.version:
        vk = version_key(run.version)
        name = " ".join(tok for tok in name.split() if version_key(tok) != vk)
    name = re.sub(r"\s*(테스트|test)\s*$", "", name, flags=re.IGNORECASE).strip()
    slug = re.sub(r"\s+", "", name)
    return slug or re.sub(r"\s+", "", (run.name or "").strip()) or "run"


def report_filename(project_name: str, run: TestRun, ext: str, when: datetime = None) -> str:
    """내려받을 파일 이름: {프로젝트}_{수행}_Test_Report_{YYYYMMDD}.{ext}

    예: Starfort_계정·세션정책_Test_Report_20260930.pdf (09-30 사용자 형식). 날짜는 내려받는 날이다.
    예전 이름 {프로젝트}_Report_R{회차} 는 어느 테스트인지 몰라 파일만 보고 구분할 수 없었다.
    """
    day = (when or report_now()).strftime("%Y%m%d")
    project = _safe_name(project_name) or "report"
    return f"{project}_{_safe_name(_run_slug(project_name, run))}_Test_Report_{day}.{ext}"


def _fmt_dt(iso) -> str:
    """ISO 문자열을 'YYYY-MM-DD HH:MM' 로. 없으면 '-'."""
    return iso.replace("T", " ")[:16] if iso else "-"


# ── JSON report ───────────────────────────────────────────────────────────────

@router.get("")
def report_json(
    project_id: int,
    run_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    project = _get_project_or_404(project_id, db)
    run = _get_run_or_404(project_id, run_id, db)
    raw = _build_report_data(run, db)

    # Map to frontend ReportData format
    summary = raw["summary"]
    return {
        "project": {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "jira_base_url": project.jira_base_url,
            "issue_tracker": project.issue_tracker,
            "created_by": project.created_by,
            "created_at": project.created_at.isoformat() if project.created_at else None,
            "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        },
        "test_run": raw["run"],
        "summary": {
            "total": summary["total"],
            # ★`pass_rate` 의 분모만 수행분(pass+fail+block)이고 나머지 넷은 전체다.
            #   이름만으로는 알 수 없어 다섯을 더하면 100 이 되리라 기대하게 되므로
            #   분모를 함께 낸다. 합격률을 전체 기준으로 되돌리면 미수행이 많은
            #   수행에서 실제보다 낮게 보이던 SYM-57 로 돌아간다.
            "executed": summary["executed"],
            "pass": summary["passed"],
            "fail": summary["failed"],
            "block": summary["blocked"],
            "na": summary["na"],
            "not_started": summary["ns"],
            "pass_rate": summary["pass_rate"],
            "fail_rate": round(summary["failed"] / summary["total"] * 100, 1) if summary["total"] > 0 else 0.0,
            "block_rate": round(summary["blocked"] / summary["total"] * 100, 1) if summary["total"] > 0 else 0.0,
            "na_rate": round(summary["na"] / summary["total"] * 100, 1) if summary["total"] > 0 else 0.0,
            "not_started_rate": round(summary["ns"] / summary["total"] * 100, 1) if summary["total"] > 0 else 0.0,
        },
        # 이름은 호환을 위해 두지만 FAIL 과 BLOCK 을 함께 싣는다. result 가 실제 값이다.
        "top_failures": [
            {
                "test_case": {
                    "tc_id": f["tc_id"],
                    "priority": f["priority"],
                    "category": f["category"],
                },
                "result": f["result"],
                "actual_result": f.get("actual_result"),
                "issue_link": f.get("issue_link"),
                "executed_by": f.get("executed_by"),
            }
            for f in raw["issue_items"]
        ],
        "jira_issues": raw["related_issues"],
        "issues": raw["run_issues"],
        "issue_summary": _issue_summary(raw["run_issues"]),
        "issue_candidates": _issue_candidates(run, raw["run_issues"], db),
        "category_summary": [
            {
                "category": c["category"],
                "total": c["total"],
                "pass": c["passed"],
                "fail": c["failed"],
                "block": c["blocked"],
                "na": c.get("na", 0),
                "not_started": c.get("not_started", 0),
                "pass_rate": c["pass_rate"],
            }
            for c in raw["categories"]
        ],
        "priority_summary": [
            {
                "priority": p["priority"],
                "total": p["total"],
                "pass": p["passed"],
                "fail": p["failed"],
                "block": p["blocked"],
                "na": p["na"],
                "not_started": p["not_started"],
                "pass_rate": p["pass_rate"],
            }
            for p in raw["priorities"]
        ],
        "comparison": raw["comparison"],
        "executors": raw["executors"],
        "total_duration_sec": raw["total_duration_sec"],
    }


# ── PDF report ────────────────────────────────────────────────────────────────

# 리포트 PDF·엑셀 요약 시트의 문구. 화면 언어를 따른다(lang). 웹 리포트(i18n report.json)와 같은 말을 쓴다.
REPORT_TEXT = {
    "ko": {
        "title": "{project} 테스트 리포트",
        "project_info": "프로젝트 정보", "project": "프로젝트", "run_name": "테스트 수행",
        "version": "버전", "environment": "환경", "round": "라운드", "status": "상태",
        "created": "생성일", "completed": "완료일", "executors": "수행자", "duration": "기록된 소요 시간",
        "status_in_progress": "진행 중", "status_completed": "완료",
        "overall": "전체 현황", "total_tc": "전체 TC", "not_started": "미수행",
        "pass_rate_note": "PASS / (PASS+FAIL+BLOCK)",
        "comparison": "수행 비교",
        "comparison_base": "비교 대상: {name} (R{round}) · 두 수행 모두에서 수행한 TC {common}건",
        "changed": "결과가 변경된 TC", "regressions": "퇴보 (PASS -> FAIL)", "fixed": "개선 (FAIL -> PASS)",
        # 수행 비교 카드 넷(09-30 결정). "결과가 변경된 TC" 카드는 수정 수와 겹쳐 보여 뺐다.
        "prev_fail_tc": "이전 실패 TC", "prev_fail_sub": "이전 수행 FAIL",
        "fixed_tc": "수정된 TC", "fixed_sub": "FAIL -> PASS",
        "still_tc": "미수정 TC", "still_sub": "FAIL -> FAIL",
        "regressed_tc": "퇴보 TC", "regressed_sub": "PASS -> FAIL",
        "change_list": "변경 상세", "change": "변경", "kind": "구분", "related_issues": "연관 이슈",
        "kind_regression": "퇴보", "kind_still": "미수정", "kind_fixed": "개선", "kind_other": "변경",
        "issues": "이슈", "issues_tool": "이슈 ({tool})",
        # 이슈 표: 상태 = QA 판정(verdict), 심각도 = note 칸. 이슈 관리 도구의 상태(status)는 싣지 않는다(09-30).
        "key": "키", "issue_title": "제목", "related_tc": "연관 TC", "note": "심각도",
        "origin": "발견", "origin_this": "이번 수행", "verdict": "상태",
        "verdict_resolved": "해결", "verdict_open": "유지", "verdict_partial": "부분 해결",
        "verdict_unverified": "미확인", "verdict_new": "신규",
        "group_open": "미해결", "group_resolved": "처리 완료",
        "issue_summary": "미해결 {open} · 처리 완료 {resolved}",
        "issue_summary_unverified": " (미해결 중 미확인 {unverified})",
        "resolved_candidate": "해결 후보",
        "failures": "실패·차단 항목", "no_failures": "실패하거나 차단된 항목이 없습니다.",
        "failures_note": "절차와 기대 결과 전문은 Excel 리포트의 Results 시트에 있습니다.",
        "tc_id": "TC ID", "priority": "우선순위", "category": "카테고리", "result": "결과",
        "actual": "실제 결과", "issue_link": "이슈 링크",
        "priority_summary": "우선순위별 요약", "category_summary": "카테고리별 요약",
        "unset_priority": "(미지정)", "unset_category": "(미분류)",
        "generated": "생성 {when}",
        # 엑셀 요약 시트 전용
        "xl_executed": "수행", "xl_issues_count": "이슈 ({count}건)", "xl_url": "링크",
        "xl_compared_with": "비교 대상: {name} (R{round})", "xl_common": "양쪽 모두 수행",
        "xl_regressions": "퇴보", "xl_fixed": "개선",
    },
    "en": {
        "title": "{project} Test Report",
        "project_info": "Project Info", "project": "Project", "run_name": "Test run",
        "version": "Version", "environment": "Environment", "round": "Round", "status": "Status",
        "created": "Created", "completed": "Completed", "executors": "Executed by", "duration": "Recorded duration",
        "status_in_progress": "In progress", "status_completed": "Completed",
        "overall": "Overall Status", "total_tc": "Total TC", "not_started": "Not started",
        "pass_rate_note": "PASS / (PASS+FAIL+BLOCK)",
        "comparison": "Run Comparison",
        "comparison_base": "Baseline: {name} (R{round}) · {common} TCs executed in both runs",
        "changed": "Changed TCs", "regressions": "Regressions (PASS -> FAIL)", "fixed": "Fixed (FAIL -> PASS)",
        "prev_fail_tc": "Previously failed TCs", "prev_fail_sub": "FAIL in previous run",
        "fixed_tc": "Fixed TCs", "fixed_sub": "FAIL -> PASS",
        "still_tc": "Still failing TCs", "still_sub": "FAIL -> FAIL",
        "regressed_tc": "Regressed TCs", "regressed_sub": "PASS -> FAIL",
        "change_list": "Change details", "change": "Change", "kind": "Kind", "related_issues": "Related issues",
        "kind_regression": "Regression", "kind_still": "Still failing", "kind_fixed": "Fixed", "kind_other": "Changed",
        "issues": "Issues", "issues_tool": "Issues ({tool})",
        "key": "Key", "issue_title": "Title", "related_tc": "Related TCs", "note": "Severity",
        "origin": "Found in", "origin_this": "This run", "verdict": "Status",
        "verdict_resolved": "Resolved", "verdict_open": "Still open", "verdict_partial": "Partially fixed",
        "verdict_unverified": "Unverified", "verdict_new": "New",
        "group_open": "Unresolved", "group_resolved": "Resolved",
        "issue_summary": "Unresolved {open} · Resolved {resolved}",
        "issue_summary_unverified": " ({unverified} of them unverified)",
        "resolved_candidate": "likely resolved",
        "failures": "Failed / Blocked", "no_failures": "No failed or blocked test cases.",
        "failures_note": "Full steps and expected results are in the Results sheet of the Excel report.",
        "tc_id": "TC ID", "priority": "Priority", "category": "Category", "result": "Result",
        "actual": "Actual Result", "issue_link": "Issue Link",
        "priority_summary": "By Priority", "category_summary": "By Category",
        "unset_priority": "(none)", "unset_category": "(none)",
        "generated": "Generated {when}",
        # Excel summary sheet only
        "xl_executed": "Executed", "xl_issues_count": "Issues ({count})", "xl_url": "URL",
        "xl_compared_with": "Compared with: {name} (R{round})", "xl_common": "Executed in both",
        "xl_regressions": "Regression", "xl_fixed": "Improved",
    },
}

# 웹 리포트와 같은 색이다(index.css 의 라이트 테마 값).
_C = {
    "text": (30, 41, 59), "muted": (100, 116, 139), "line": (226, 232, 240), "soft": (248, 250, 252),
    "head": (241, 245, 249), "accent": (37, 99, 235), "link": (37, 99, 235),
    "PASS": (26, 127, 55), "FAIL": (207, 34, 46), "BLOCK": (191, 135, 0), "NA": (99, 102, 241), "NS": (148, 163, 184),
}
_TRACKER_NAME = {"jira": "Jira", "linear": "Linear"}
#: 수행 비교 변경 상세의 구분 색. 퇴보·미수정은 FAIL, 개선은 PASS, 그 밖은 본문색.
_KIND_COLOR = {"regression": _C["FAIL"], "still": _C["FAIL"], "fixed": _C["PASS"], "other": _C["text"]}

#: 이슈 묶음 색. 웹 묶음 행·PDF 소제목·엑셀 소제목이 같은 색이다.
_GROUP_COLOR = {"open": _C["FAIL"], "resolved": _C["PASS"]}
_GROUP_HEX = {g: "%02X%02X%02X" % c for g, c in _GROUP_COLOR.items()}


def _report_lang(lang) -> str:
    return "en" if str(lang or "").lower().startswith("en") else "ko"


@router.get("/pdf")
def report_pdf(
    project_id: int,
    run_id: int = None,
    lang: str = "ko",
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    """리포트 PDF. 웹 리포트 화면과 같은 차례와 모양이다.

    ★웹과 같은 차례로 싣는다: 정보 -> 전체 현황 -> 수행 비교 -> 이슈 -> 실패·차단 ->
      우선순위별 -> 카테고리별. 예전 PDF 는 차례도 달랐고, 실패 항목마다 절차와 기대
      결과 전문을 쏟아 2~4쪽이 글 덩어리가 됐다. 한 장으로 이번 수행을 보는 것이
      목적이라 실패·차단은 웹처럼 한 줄 표로 두고, 전문은 엑셀 Results 시트에 맡긴다.
    ★문구는 화면 언어(lang)를 따른다. 예전에는 제목·항목·상태 값이 모두 영문이었다.
    """
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    project = _get_project_or_404(project_id, db)
    run = _get_run_or_404(project_id, run_id, db)
    data = _build_report_data(run, db)
    T = REPORT_TEXT[_report_lang(lang)]
    generated_at = _fmt_dt(report_now().isoformat())

    class ReportPDF(FPDF):
        def footer(self):
            self.set_y(-12)
            self.set_font(font_name, "", 7.5)
            self.set_text_color(*_C["muted"])
            self.cell(self.epw / 2, 5, T["generated"].format(when=generated_at))
            self.cell(self.epw / 2, 5, f"{self.page_no()} / {{nb}}", align="R")

    pdf = ReportPDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    font_name = _load_pdf_font(pdf)
    pdf.add_page()
    pdf.set_draw_color(*_C["line"])

    def color(key):
        pdf.set_text_color(*_C[key])

    def heading(text, extra_space=24):
        # 제목만 페이지 끝에 홀로 남지 않도록 제목 + 첫 줄이 안 들어가면 넘긴다
        if pdf.will_page_break(10 + extra_space):
            pdf.add_page()
        pdf.ln(4)
        pdf.set_font(font_name, "B", 12.5)
        color("text")
        pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    def note(text, size=8.5):
        pdf.set_font(font_name, "", size)
        color("muted")
        pdf.multi_cell(0, 5, text, new_x="LMARGIN", new_y="NEXT")

    head_style = FontFace(family=font_name, emphasis="BOLD", color=_C["muted"], fill_color=_C["head"], size_pt=8.5)

    def table(headers, rows, widths, align, cell_styles=None, links=None):
        """웹 표처럼 가로줄만 긋는다. 긴 글은 칸 안에서 줄을 변경하고, 쪽을 넘기면 머리행을 다시 그린다."""
        pdf.set_font(font_name, "", 8.5)
        color("text")
        with pdf.table(
            width=pdf.epw, col_widths=widths, text_align=align, headings_style=head_style,
            borders_layout="HORIZONTAL_LINES", line_height=5, padding=(1.6, 2),
            repeat_headings=1, cell_fill_mode="NONE",
        ) as tb:
            hr = tb.row()
            for h in headers:
                hr.cell(h)
            for r_i, row in enumerate(rows):
                tr = tb.row()
                for c_i, v in enumerate(row):
                    style = (cell_styles or {}).get((r_i, c_i))
                    link = (links or {}).get((r_i, c_i))
                    tr.cell("" if v is None else str(v), style=style, link=link)
        pdf.ln(2)

    # ── 머리 · 프로젝트 정보 ────────────────────────────────────────────
    # 웹 리포트와 같은 "항목 | 값 | 항목 | 값" 표다. 항목 칸만 옅게 칠한다.
    run_info = data["run"]
    pdf.set_font(font_name, "B", 17)
    color("text")
    pdf.multi_cell(0, 9, T["title"].format(project=project.name), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    status = run_info["status"]
    rows = [
        [(T["project"], project.name), (T["run_name"], f"{run.name} (R{run.round})")],
        [(T["version"], run.version or "-"), (T["environment"], run.environment or "-")],
        [(T["round"], f"R{run.round}"), (T["status"], T.get(f"status_{status}", status))],
        [(T["created"], _fmt_dt(run_info.get("created_at"))), (T["completed"], _fmt_dt(run_info.get("completed_at")))],
    ]
    wide = []
    if data["executors"]:
        # 이름만 쉼표로 잇는다. 건수를 붙이면 "YM Seo 50" 처럼 이름의 일부로 읽힌다(09-30 지적).
        wide.append((T["executors"], ", ".join(e["name"] for e in data["executors"])))
    if data.get("total_duration_sec"):
        sec = int(data["total_duration_sec"])
        wide.append((T["duration"], f"{sec // 3600}h {sec % 3600 // 60}m" if sec >= 3600 else f"{sec // 60}m {sec % 60}s"))

    heading(T["project_info"])
    label_style = FontFace(family=font_name, emphasis="BOLD", color=_C["muted"], fill_color=_C["soft"], size_pt=8.5)
    value_style = FontFace(family=font_name, color=_C["text"], size_pt=9)
    status_style = FontFace(
        family=font_name, emphasis="BOLD", size_pt=9,
        color=_C["PASS"] if status == "completed" else _C["accent"],
    )
    pdf.set_draw_color(*_C["line"])
    with pdf.table(
        width=pdf.epw, col_widths=(13, 37, 13, 37), first_row_as_headings=False,
        borders_layout="ALL", line_height=5.5, padding=(2, 3), text_align="LEFT",
    ) as tb:
        for pair in rows:
            r = tb.row()
            for label, value in pair:
                r.cell(label, style=label_style)
                r.cell(str(value), style=status_style if label == T["status"] else value_style)
        for label, value in wide:
            r = tb.row()
            r.cell(label, style=label_style)
            r.cell(value, style=value_style, colspan=3)
    pdf.ln(2)

    # ── 전체 현황 ─────────────────────────────────────────────────────────
    heading(T["overall"], extra_space=26)
    s = data["summary"]
    boxes = [
        (T["total_tc"], s["total"], "accent"), ("PASS", s["passed"], "PASS"), ("FAIL", s["failed"], "FAIL"),
        ("BLOCK", s["blocked"], "BLOCK"), ("N/A", s["na"], "NA"), (T["not_started"], s["ns"], "NS"),
        ("PASS Rate", f"{s['pass_rate']}%" if s["pass_rate"] is not None else "-", "PASS"),
    ]
    gap = 2.5
    bw = (pdf.epw - gap * (len(boxes) - 1)) / len(boxes)
    y = pdf.get_y()
    for i, (label, value, key) in enumerate(boxes):
        x = pdf.l_margin + i * (bw + gap)
        pdf.set_fill_color(*_C["soft"])
        pdf.rect(x, y, bw, 20, style="F", round_corners=True, corner_radius=2)
        pdf.set_xy(x + 2.5, y + 2.5)
        pdf.set_font(font_name, "", 7.5)
        color("muted")
        pdf.cell(bw - 5, 4, label)
        pdf.set_xy(x + 2.5, y + 8)
        pdf.set_font(font_name, "B", 15)
        color(key)
        pdf.cell(bw - 5, 8, str(value))
    pdf.set_xy(pdf.l_margin, y + 21)
    note(T["pass_rate_note"], size=7.5)

    # ── 수행 비교 (대상이 없으면 싣지 않는다) ──────────────────────────────
    comp = data["comparison"]
    if comp:
        heading(T["comparison"])
        prev = comp["previous_run"]
        note(T["comparison_base"].format(name=prev["name"], round=prev["round"], common=comp["common"]))
        pdf.ln(1)
        pf = comp["prev_fail"]
        # 카드 넷: 이전 실패 -> 수정 -> 미수정 -> 퇴보. 8 중 7 고치고 1 남았고 새로 깨진 건 0 이 한 줄로 읽힌다.
        table(
            [f"{T['prev_fail_tc']} ({T['prev_fail_sub']})", f"{T['fixed_tc']} ({T['fixed_sub']})",
             f"{T['still_tc']} ({T['still_sub']})", f"{T['regressed_tc']} ({T['regressed_sub']})"],
            [[pf["total"], pf["fixed"], pf["still"], len(comp["regressions"])]],
            (1, 1, 1, 1), ("CENTER",) * 4,
            cell_styles={
                (0, 0): FontFace(emphasis="BOLD"),
                (0, 1): FontFace(color=_C["PASS"], emphasis="BOLD"),
                (0, 2): FontFace(color=_C["FAIL"], emphasis="BOLD"),
                (0, 3): FontFace(color=_C["FAIL"], emphasis="BOLD"),
            },
        )
        if comp["changes"]:
            pdf.set_font(font_name, "B", 9.5)
            color("text")
            pdf.cell(0, 6, f"{T['change_list']} {len(comp['changes'])}", new_x="LMARGIN", new_y="NEXT")
            table(
                [T["tc_id"], T["priority"], T["category"], T["change"], T["kind"], T["related_issues"]],
                [[c["tc_id"] or "-", c["priority"] or T["unset_priority"], c["category"] or T["unset_category"],
                  f"{c['before']} -> {c['after']}", T["kind_" + c["kind"]], ", ".join(c["issue_keys"]) or "-"]
                 for c in comp["changes"]],
                (18, 14, 22, 18, 12, 29), ("LEFT",) * 6,
                cell_styles={(n, 3): FontFace(color=_KIND_COLOR[c["kind"]], emphasis="BOLD") for n, c in enumerate(comp["changes"])}
                | {(n, 4): FontFace(color=_KIND_COLOR[c["kind"]]) for n, c in enumerate(comp["changes"])},
            )

    # ── 이슈 (등록한 것이 없으면 싣지 않는다) ──────────────────────────────
    issues = data["run_issues"]
    if issues:
        tool = _TRACKER_NAME.get(project.issue_tracker or "")
        title = T["issues_tool"].format(tool=tool) if tool else T["issues"]
        heading(f"{title} {len(issues)}")
        # ★이전 회차 이슈가 이번 수행에서 어떻게 됐는지가 종합 보고서의 핵심이라, 한 표로
        #   섞지 않고 미처리 -> 신규 -> 미확인 -> 처리 완료 묶음으로 나눠 싣는다.
        note(_issue_summary_text(issues, T), size=8.5)
        for group in ISSUE_GROUP_ORDER:
            items = [i for i in issues if i["group"] == group]
            if not items:
                continue
            # 소제목만 쪽 끝에 남고 표는 다음 쪽으로 넘어가지 않게, 머리행 + 한 줄 자리가 없으면 쪽을 넘긴다.
            if pdf.will_page_break(34):
                pdf.add_page()
            # 묶음 사이를 띄우고 소제목을 결과 색(미해결 빨강 · 처리 완료 초록)으로 구분한다.
            pdf.ln(3)
            pdf.set_font(font_name, "B", 10)
            pdf.set_text_color(*_GROUP_COLOR[group])
            pdf.cell(0, 6, f"{T['group_' + group]} {len(items)}", new_x="LMARGIN", new_y="NEXT")
            color("text")
            table(
                [T["key"], T["issue_title"], T["origin"], T["verdict"], T["related_tc"], T["note"]],
                [[i["issue_key"] or "-", i["title"], _origin_text(i, T, run.name), _verdict_text(i, T),
                  ", ".join(i["tc_ids"]) or "-", i["note"] or "-"] for i in items],
                (12, 40, 12, 12, 20, 17), ("LEFT",) * 6,
                cell_styles={(n, 0): FontFace(emphasis="BOLD") for n in range(len(items))}
                | {(n, 1): FontFace(color=_C["link"]) for n in range(len(items))},
                links={(n, 1): i["url"] for n, i in enumerate(items)},
            )

    # ── 실패·차단 ─────────────────────────────────────────────────────────
    items = data["issue_items"]
    heading(f"{T['failures']} {len(items)}")
    if not items:
        note(T["no_failures"], size=9)
    else:
        table(
            [T["tc_id"], T["priority"], T["category"], T["result"], T["actual"], T["issue_link"]],
            [[i["tc_id"] or "-", i["priority"] or T["unset_priority"], i["category"] or T["unset_category"],
              i["result"], i.get("actual_result") or "-", i.get("issue_link") or "-"] for i in items],
            (17, 12, 16, 10, 45, 24), ("LEFT", "LEFT", "LEFT", "LEFT", "LEFT", "LEFT"),
            cell_styles={(n, 3): FontFace(color=_C.get(i["result"], _C["text"]), emphasis="BOLD")
                         for n, i in enumerate(items)},
        )
        note(T["failures_note"], size=7.5)

    # ── 우선순위별 · 카테고리별 ────────────────────────────────────────────
    num_heads = ["Total", "PASS", "FAIL", "BLOCK", "N/A", T["not_started"], "PASS Rate"]
    num_align = ("LEFT",) + ("RIGHT",) * 7

    def breakdown(title, rows, name_of):
        heading(title)
        body = [[name_of(r), r["total"], r["passed"], r["failed"], r["blocked"], r.get("na", 0),
                 r.get("not_started", 0), f"{r['pass_rate']}%" if r["pass_rate"] is not None else "-"]
                for r in rows]
        styles = {}
        for n in range(len(body)):
            styles[(n, 2)] = FontFace(color=_C["PASS"])
            styles[(n, 3)] = FontFace(color=_C["FAIL"])
            styles[(n, 4)] = FontFace(color=_C["BLOCK"])
            styles[(n, 5)] = FontFace(color=_C["NA"])
            styles[(n, 7)] = FontFace(emphasis="BOLD")
        table([T["priority"] if title == T["priority_summary"] else T["category"]] + num_heads,
              body, (30, 10, 10, 10, 10, 10, 11, 13), num_align, cell_styles=styles)

    if data["priorities"]:
        breakdown(T["priority_summary"], data["priorities"], lambda r: r["priority"] or T["unset_priority"])
    if data["categories"]:
        breakdown(T["category_summary"], data["categories"], lambda r: r["category"] or T["unset_category"])

    output = io.BytesIO()
    pdf.output(output)
    output.seek(0)

    from urllib.parse import quote
    encoded = quote(report_filename(project.name, run, "pdf"))
    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


# 본문이 이보다 길면 잘라 "..." 를 붙인다. 전문은 엑셀 Results 시트에 있다.
PDF_TEXT_LIMIT = 300


def _origin_text(issue: dict, T: dict, run_name: str = None) -> str:
    """발견 회차. 이전 회차면 R{n}, 아니면 "이번 수행".

    이름이 다른 수행에서 가져온 이슈는 "이름 R{n}" 으로 어느 수행인지 밝힌다. 같은
    이름의 이전 회차면 회차만으로 충분하다.
    """
    if issue.get("origin_round") is None:
        return T["origin_this"]
    text = f"R{issue['origin_round']}"
    name = issue.get("origin_run_name")
    if name and run_name is not None and name != run_name:
        text = f"{name} {text}"
    return text


def _is_unverified(issue: dict) -> bool:
    """이전 회차 이슈인데 아직 판정하지 않은 것. 해결 후보 표시와 요약 줄의 미확인 수에 쓴다.
    이번 수행에서 새로 넣은 이슈는 확인 대상이 아니다."""
    return issue.get("origin_round") is not None and issue.get("verdict") in (None, "unverified")


def _verdict_text(issue: dict, T: dict) -> str:
    """판정 문구. 이번 수행에서 새로 넣은 이슈는 판정 대신 "신규"(09-30 사용자 지시), 이전 회차
    이슈인데 판정이 없으면 "-", 미확인인데 연관 TC 가 전부 PASS 면 해결 후보를 덧붙인다."""
    v = issue.get("verdict")
    if v:
        text = T[f"verdict_{v}"]
    else:
        text = T["verdict_new"] if issue.get("origin_round") is None else "-"
    if _is_unverified(issue) and issue.get("tcs_all_pass"):
        text += f" ({T['resolved_candidate']})"
    return text


def _clip(text) -> str:
    text = str(text)
    return text if len(text) <= PDF_TEXT_LIMIT else text[:PDF_TEXT_LIMIT] + "... (full text in Excel)"


def _fit(pdf, text: str, width: float) -> str:
    """칸 폭에 맞게 자르고 잘렸으면 '...' 를 붙인다. 글자 수가 아니라 실제 폭으로 잰다."""
    if pdf.get_string_width(text) <= width:
        return text
    while text and pdf.get_string_width(text + "...") > width:
        text = text[:-1]
    return text + "..."


def _load_pdf_font(pdf) -> str:
    """한글 폰트를 등록하고 이름을 돌려준다. 굵은체 파일이 없으면 일반체로 대신한다.

    ★굵은체("B")에 일반체 파일을 등록하면 제목이 굵게 나오지 않는다. 예전 코드가
      그랬다. 두 파일을 따로 찾는다.
    """
    here = os.path.join(os.path.dirname(__file__), "..", "fonts")
    candidates = [
        # ★레포에 넣어 둔 Pretendard(OFL-1.1, backend/fonts/OFL.txt)가 먼저다.
        #   시스템 폰트에만 기대면 한글 폰트가 없는 리눅스 서버와 CI 에서 Helvetica 로
        #   떨어지고, 한글이 한 글자만 있어도 PDF 가 FPDFUnicodeEncodingException 으로
        #   500 이 된다. 맑은 고딕은 재배포가 안 되므로 레포에 넣지 않는다.
        #   같은 배포본의 OTF 판이 아니라 TTF 판(static/alternative)을 쓴다.
        (os.path.join(here, "Pretendard-Regular.ttf"), os.path.join(here, "Pretendard-Bold.ttf")),
        ("C:/Windows/Fonts/malgun.ttf", "C:/Windows/Fonts/malgunbd.ttf"),
        ("/usr/share/fonts/truetype/nanum/NanumGothic.ttf", "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf"),
    ]
    for regular, bold in candidates:
        if os.path.exists(regular):
            # ★uni 인자는 fpdf2 2.5.1 부터 폐기됐고 앞으로 제거된다.
            #   지금은 TTF 가 기본 유니코드라 인자 없이 같은 동작이다.
            pdf.add_font("KoreanFont", "", regular)
            pdf.add_font("KoreanFont", "B", bold if os.path.exists(bold) else regular)
            return "KoreanFont"
    logger.warning(
        "한글 폰트를 찾을 수 없습니다. PDF에 한글이 깨질 수 있습니다. 탐색 경로: %s",
        [c[0] for c in candidates],
    )
    return "Helvetica"


# ── Excel report ──────────────────────────────────────────────────────────────

@router.get("/excel")
def report_excel(
    project_id: int,
    run_id: int = None,
    lang: str = "ko",
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    project = _get_project_or_404(project_id, db)
    run = _get_run_or_404(project_id, run_id, db)

    # 웹과 PDF 가 쓰는 집계를 그대로 쓴다. 파일마다 따로 세면 세 산출물이 갈라진다.
    data = _build_report_data(run, db)
    summary = data["summary"]
    # ★요약 시트 문구는 PDF 와 같은 표에서, 화면 언어(lang)를 따른다. 예전에는 전부 영문이었다.
    #   Results 시트는 수행 엑셀(routes/testruns.py)과 열 이름이 같아야 해서 그대로 둔다.
    T = REPORT_TEXT[_report_lang(lang)]

    # Excel 결과 시트용: 1회만 조회 (이중 로드 제거), 필요한 컬럼만 load
    results = (
        db.query(TestResult)
        .options(
            joinedload(TestResult.test_case).load_only(
                TestCase.no, TestCase.tc_id, TestCase.type, TestCase.category,
                TestCase.depth1, TestCase.depth2, TestCase.priority,
                TestCase.test_type, TestCase.precondition,
                TestCase.test_steps, TestCase.expected_result,
                # 시트 순서로 세우려면 필요하다. 빼면 행마다 지연 로딩이 붙는다.
                TestCase.sheet_name,
            )
        )
        .filter(TestResult.test_run_id == run.id)
        # 런에 나중에 편입된 TC가 뒤에 붙지 않도록 TC 번호 순으로 고정한다
        .join(TestCase, TestResult.test_case_id == TestCase.id)
        .order_by(TestCase.no)
        .all()
    )
    # ★수행 엑셀과 같은 차례로 세운다. 같은 수행을 두 파일로 뽑을 수 있어서,
    #   한쪽만 고치면 같은 행이 다른 번호를 단다.
    results = sort_results_for_export(results, leaf_sheet_order(project_id, db))

    wb = Workbook()

    # ── Summary sheet ─────────────────────────────────────────────────────
    ws_summary = wb.active
    ws_summary.title = "Summary"

    dark_fill = PatternFill(start_color="2F3136", end_color="2F3136", fill_type="solid")
    header_font = Font(name="Malgun Gothic", bold=True, color="FFFFFF", size=10)
    title_font = Font(name="Malgun Gothic", bold=True, size=14)
    section_font = Font(name="Malgun Gothic", bold=True, size=11)
    cell_font = Font(name="Malgun Gothic", size=10)
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    center = Alignment(horizontal="center", vertical="center")

    pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    block_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")

    ws_summary.merge_cells("B1:I1")
    ws_summary["B1"].value = safe_cell(T["title"].format(project=project.name))
    ws_summary["B1"].font = title_font

    run_info = data["run"]
    status = run_info["status"]
    info_lines = [
        f"{T['run_name']}: {run.name}",
        f"{T['version']}: {run.version or 'N/A'}  |  {T['environment']}: {run.environment or 'N/A'}  |  {T['round']}: R{run.round}",
        f"{T['status']}: {T.get(f'status_{status}', status)}  |  {T['created']}: {_fmt_dt(run_info['created_at'])}"
        f"  |  {T['completed']}: {_fmt_dt(run_info['completed_at'])}",
    ]
    if data["executors"]:
        info_lines.append(f"{T['executors']}: " + ", ".join(e["name"] for e in data["executors"]))
    for i, line in enumerate(info_lines):
        ws_summary.cell(row=3 + i, column=2, value=safe_cell(line)).font = cell_font

    def write_table(start_row, title, headers, rows, rate_col=None):
        """제목 한 줄 + 표. 다음에 쓸 행 번호를 돌려준다.

        합격률 칸은 숫자(0~1)에 백분율 서식을 준다. 문자열 "92.0%" 로 넣으면
        엑셀에서 정렬도 계산도 안 된다.
        """
        ws_summary.cell(row=start_row, column=2, value=title).font = section_font
        hr = start_row + 1
        for i, h in enumerate(headers):
            c = ws_summary.cell(row=hr, column=2 + i, value=h)
            c.font, c.fill, c.alignment, c.border = header_font, dark_fill, center, thin_border
        for r_i, row in enumerate(rows, 1):
            for i, v in enumerate(row):
                if i == rate_col:
                    v = None if v is None else round(v / 100, 3)
                c = ws_summary.cell(row=hr + r_i, column=2 + i, value=safe_cell(v))
                c.font, c.alignment, c.border = cell_font, center, thin_border
                if i == rate_col:
                    c.number_format = "0.0%"
        return hr + len(rows) + 2

    row = 3 + len(info_lines) + 1
    # 결과 값 이름(PASS·FAIL·BLOCK·N/A)은 웹·PDF 와 같이 언어와 무관하게 쓴다.
    num_heads = ["PASS", "FAIL", "BLOCK", "N/A", T["not_started"], "PASS Rate"]
    row = write_table(
        row, T["overall"],
        [T["total_tc"], T["xl_executed"]] + num_heads,
        [[summary["total"], summary["executed"], summary["passed"], summary["failed"],
          summary["blocked"], summary["na"], summary["ns"], summary["pass_rate"]]],
        rate_col=7,
    )

    comp = data["comparison"]
    if comp:
        prev = comp["previous_run"]
        pf = comp["prev_fail"]
        row = write_table(
            row, safe_cell(T["xl_compared_with"].format(name=prev["name"], round=prev["round"])),
            [T["xl_common"], T["prev_fail_tc"], T["fixed_tc"], T["still_tc"], T["regressed_tc"]],
            [[comp["common"], pf["total"], pf["fixed"], pf["still"], len(comp["regressions"])]],
        )
        if comp["changes"]:
            row = write_table(
                row, T["change_list"],
                [T["tc_id"], T["priority"], T["category"], T["change"], T["kind"], T["related_issues"]],
                [[c["tc_id"], c["priority"] or T["unset_priority"], c["category"] or T["unset_category"],
                  f"{c['before']} -> {c['after']}", T["kind_" + c["kind"]], ", ".join(c["issue_keys"]) or None]
                 for c in comp["changes"]],
            )

    # ★이슈는 따로 시트를 두지 않고 요약 시트에 싣는다. 리포트는 한 장으로 이번
    #   수행을 다 보여 주는 것이 목적이라, 첫 시트만 열어도 보여야 한다.
    if data["run_issues"]:
        # 요약 표들과 열을 같이 쓰므로 제목(C:D)은 병합해 넓힌다. 열 폭을 늘리면 위아래
        # 숫자 표가 함께 벌어진다. 미처리 -> 신규 -> 미확인 -> 처리 완료 묶음으로 나눠 싣는다(PDF 와 같다).
        spans = [(T["key"], 2, 2), (T["issue_title"], 3, 4), (T["origin"], 5, 5), (T["verdict"], 6, 6),
                 (T["related_tc"], 7, 7), (T["note"], 8, 8), (T["xl_url"], 9, 9)]
        wrap_labels = (T["issue_title"], T["xl_url"], T["related_tc"], T["verdict"])
        left = Alignment(horizontal="left", vertical="center", wrap_text=True)
        ws_summary.cell(row=row, column=2,
                        value=T["xl_issues_count"].format(count=len(data["run_issues"]))).font = section_font
        ws_summary.cell(row=row + 1, column=2,
                        value=_issue_summary_text(data["run_issues"], T)).font = cell_font
        row += 2
        for group in ISSUE_GROUP_ORDER:
            items = [i for i in data["run_issues"] if i["group"] == group]
            if not items:
                continue
            # 소제목은 묶음 색(PDF·웹과 같다). 묶음 사이 빈 줄은 아래 row 계산이 준다.
            ws_summary.cell(row=row, column=2, value=f"{T['group_' + group]} ({len(items)})").font = Font(
                name="Malgun Gothic", bold=True, size=10, color=_GROUP_HEX[group])
            hr = row + 1
            for label, c1, c2 in spans:
                if c2 > c1:
                    ws_summary.merge_cells(start_row=hr, start_column=c1, end_row=hr, end_column=c2)
                for col in range(c1, c2 + 1):
                    ws_summary.cell(row=hr, column=col).border = thin_border
                c = ws_summary.cell(row=hr, column=c1, value=label)
                c.font, c.fill, c.alignment = header_font, dark_fill, center
            for n, issue in enumerate(items, 1):
                r = hr + n
                # 판정이 없으면 빈 칸. "-" 는 safe_cell 이 수식 방지 접두어를 붙여 '- 로 보인다.
                verdict_text = _verdict_text(issue, T)
                values = [issue["issue_key"], issue["title"], _origin_text(issue, T, run.name),
                          None if verdict_text == "-" else verdict_text,
                          ", ".join(issue["tc_ids"]) or None, issue["note"], issue["url"]]
                for (label, c1, c2), val in zip(spans, values):
                    if c2 > c1:
                        ws_summary.merge_cells(start_row=r, start_column=c1, end_row=r, end_column=c2)
                    for col in range(c1, c2 + 1):
                        ws_summary.cell(row=r, column=col).border = thin_border
                    c = ws_summary.cell(row=r, column=c1, value=safe_cell(val))
                    c.font = cell_font
                    c.alignment = left if label in wrap_labels else center
                # 주소는 스키마가 http(s) 만 받으므로 링크로 걸어도 된다.
                ws_summary.cell(row=r, column=9).hyperlink = issue["url"]
            # 묶음 사이에 빈 줄 하나. 마지막 묶음 뒤도 같아서 다음 표와 한 줄 띈다(write_table 과 같다).
            row = hr + len(items) + 2

    if data["priorities"]:
        row = write_table(
            row, T["priority_summary"],
            [T["priority"], T["total_tc"]] + num_heads,
            [[p["priority"] or T["unset_priority"], p["total"], p["passed"], p["failed"], p["blocked"],
              p["na"], p["not_started"], p["pass_rate"]] for p in data["priorities"]],
            rate_col=7,
        )

    if data["categories"]:
        row = write_table(
            row, T["category_summary"],
            [T["category"], T["total_tc"]] + num_heads,
            [[c["category"] or T["unset_category"], c["total"], c["passed"], c["failed"], c["blocked"],
              c.get("na", 0), c.get("not_started", 0), c["pass_rate"]] for c in data["categories"]],
            rate_col=7,
        )

    ws_summary.column_dimensions["B"].width = 18
    for col in range(3, 10):
        ws_summary.column_dimensions[get_column_letter(col)].width = 12

    # ── Results sheet ─────────────────────────────────────────────────────
    ws_results = wb.create_sheet("Results")

    # ★같은 런을 뽑는 수행 엑셀(routes/testruns.py)과 열 집합이 같아야 한다.
    #   한쪽에만 열을 더하면 두 파일이 조용히 갈라진다.
    res_headers = [
        "No", "TC ID", "Type", "Category", "Depth1", "Depth2",
        "Priority", "Platform", "Precondition", "Steps", "Expected Result", "Result",
        "Actual Result", "Issue Link", "Remarks",
    ]
    res_widths = [6, 10, 10, 15, 18, 18, 10, 12, 30, 35, 35, 10, 35, 20, 20]
    assert len(res_headers) == len(res_widths), (
        f"헤더 {len(res_headers)}개 != 폭 {len(res_widths)}개. zip 이 조용히 잘라 낸다"
    )

    for i, (h, w) in enumerate(zip(res_headers, res_widths)):
        col = i + 1
        cell = ws_results.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = dark_fill
        cell.alignment = center
        cell.border = thin_border
        ws_results.column_dimensions[get_column_letter(col)].width = w

    for row_idx, r in enumerate(results, 2):
        tc = r.test_case
        result_val = r.result.value if hasattr(r.result, "value") else r.result
        row_values = [
            # ★No 는 저장된 no 가 아니라 이 목록의 순번이다(수행 엑셀과 같은 규약).
            row_idx - 1, tc.tc_id, tc.type, tc.category, tc.depth1, tc.depth2,
            tc.priority, tc.test_type, tc.precondition, tc.test_steps, tc.expected_result,
            result_val, r.actual_result, r.issue_link, r.remarks,
        ]
        assert len(row_values) == len(res_headers), "값 개수가 헤더와 다르다"
        for col_idx, val in enumerate(row_values, 1):
            # 사용자가 쓴 값은 그대로 넣지 않는다. =, +, -, @ 로 시작하면 여는 쪽에서
            # 수식으로 실행된다(CWE-1236).
            cell = ws_results.cell(row=row_idx, column=col_idx, value=safe_cell(val))
            cell.font = cell_font
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center", wrap_text=True)

            # Color the result column
            # ★열 번호를 박지 않는다. 앞에 열을 끼우면 조용히 엉뚱한 칸이 칠해진다.
            if col_idx == res_headers.index("Result") + 1:
                cell.alignment = center
                if result_val == "PASS":
                    cell.fill = pass_fill
                elif result_val == "FAIL":
                    cell.fill = fail_fill
                elif result_val == "BLOCK":
                    cell.fill = block_fill

    ws_results.freeze_panes = "A2"

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    from urllib.parse import quote
    encoded = quote(report_filename(project.name, run, "xlsx"))
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
