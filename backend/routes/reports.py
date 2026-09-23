import io
import os
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
)
from services.excel_safe import safe_cell
from services.sheet_order import leaf_sheet_order, sort_results_for_export
from auth import get_current_user, check_project_access

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/projects/{project_id}/reports",
    tags=["reports"],
)


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
    # NULL 과 빈 문자열이 둘 다 Uncategorized 가 되므로 한 줄로 합친다. 따로 두면 같은
    # 이름의 행이 두 번 나온다.
    merged: dict = {}
    for r in rows:
        name = (r.category or "").strip() or "Uncategorized"
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
# 우선순위를 비운 TC 를 PDF/엑셀에 적을 때의 이름. 파일의 다른 머리글이 영문이라 맞춘다.
# JSON 에는 null 로 보내고 화면이 번역한다.
UNSET_PRIORITY = "(none)"


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
            "priority": r.test_case.priority,
            "category": r.test_case.category,
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


def _previous_run(run: TestRun, db: Session):
    """같은 프로젝트에서 이 런보다 먼저 만든 런 중 가장 최근 것."""
    q = db.query(TestRun).filter(TestRun.project_id == run.project_id, TestRun.id != run.id)
    if run.created_at is not None:
        q = q.filter(
            (TestRun.created_at < run.created_at)
            | ((TestRun.created_at == run.created_at) & (TestRun.id < run.id))
        )
    else:
        q = q.filter(TestRun.id < run.id)
    return q.order_by(TestRun.created_at.desc(), TestRun.id.desc()).first()


def _comparison(run: TestRun, db: Session):
    """직전 런 대비 변화. 판정 기준은 수행 비교 화면(CompareView)과 같다.

    ★퇴보는 PASS -> FAIL, 개선은 FAIL -> PASS 다. 수행 비교 화면과 같은 판정이라
      여기서만 바꾸면 같은 두 런을 두 화면이 다른 숫자로 보여 준다.
    ★"변경" 은 두 런에서 모두 수행한(NS 가 아닌) TC 만 센다. 비교 화면과 다른 점이다.
      직전 런이 진행 중이면 대부분 NS 라서, 그대로 세면 NS -> PASS 가 전부 변경으로
      잡힌다(실측: run 25 의 변경 8건이 모두 NS -> PASS 였다).
    """
    prev = _previous_run(run, db)
    if prev is None:
        return None

    def result_map(run_id):
        rows = (
            db.query(TestResult.test_case_id, TestResult.result, TestCase.tc_id, TestCase.priority)
            .join(TestCase, TestResult.test_case_id == TestCase.id)
            .filter(TestResult.test_run_id == run_id)
            .all()
        )
        return {
            r.test_case_id: (r.result.value if hasattr(r.result, "value") else r.result, r.tc_id, r.priority)
            for r in rows
        }

    before, after = result_map(prev.id), result_map(run.id)
    common = [
        tid for tid in after
        if tid in before and before[tid][0] != "NS" and after[tid][0] != "NS"
    ]
    changed, regressions, fixed = 0, [], []
    for tid in common:
        old = before[tid][0]
        new, tc_id, priority = after[tid]
        if old == new:
            continue
        changed += 1
        item = {"tc_id": tc_id, "priority": priority, "before": old, "after": new}
        if old == "PASS" and new == "FAIL":
            regressions.append(item)
        elif old == "FAIL" and new == "PASS":
            fixed.append(item)

    def order(items):
        return sorted(items, key=lambda x: (priority_sort_key(x["priority"]), x["tc_id"] or ""))

    return {
        "previous_run": {"id": prev.id, "name": prev.name, "round": prev.round},
        "common": len(common),
        "changed": changed,
        "regressions": order(regressions),
        "fixed": order(fixed),
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
        "executors": [{"name": r[0], "count": r[1]} for r in rows],
        "total_duration_sec": round(total_sec, 1) if total_sec else None,
    }


def _related_issues(items: list) -> list:
    """이슈 링크를 항목 차례대로 중복 없이. set 을 거치면 재시작마다 순서가 바뀐다."""
    return list(dict.fromkeys(i["issue_link"] for i in items if i.get("issue_link")))


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
        },
        "summary": summary,
        "categories": categories,
        "priorities": _priority_summary_sql(run.id, db),
        "issue_items": items,
        "related_issues": _related_issues(items),
        "comparison": _comparison(run, db),
        **_executors(run.id, db),
    }


def report_filename(project_name: str, run: TestRun, ext: str) -> str:
    """내려받을 파일 이름. Windows 에서 못 쓰는 글자는 밑줄로 바꾼다."""
    bad = set(chr(92) + '/:*?"<>|')
    safe = "".join("_" if ch in bad or ord(ch) < 32 else ch for ch in project_name).strip()
    return f"{safe or 'report'}_Report_R{run.round}.{ext}"


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

@router.get("/pdf")
def report_pdf(
    project_id: int,
    run_id: int = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(check_project_access("viewer")),
):
    from fpdf import FPDF

    if not run_id:
        raise HTTPException(status_code=400, detail="run_id is required")
    project = _get_project_or_404(project_id, db)
    run = _get_run_or_404(project_id, run_id, db)
    data = _build_report_data(run, db)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    font_name = _load_pdf_font(pdf)

    def heading(text):
        # 제목만 페이지 끝에 홀로 남지 않도록, 제목 + 첫 두 줄이 안 들어가면 넘긴다
        if pdf.will_page_break(10 + 16):
            pdf.add_page()
        pdf.set_font(font_name, "B", 13)
        pdf.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")

    def table(headers, rows, first_col_ratio=None):
        """칸 폭은 본문 폭(epw)에서 나눈다. 숫자로 박으면 칸을 더할 때 페이지 밖으로 샌다."""
        n = len(headers)
        if first_col_ratio:
            first = pdf.epw * first_col_ratio
            widths = [first] + [(pdf.epw - first) / (n - 1)] * (n - 1)
        else:
            widths = [pdf.epw / n] * n
        def header_row():
            pdf.set_fill_color(240, 240, 240)
            pdf.set_font(font_name, "B", 9)
            for h, w in zip(headers, widths):
                pdf.cell(w, 8, h, border=1, align="C", fill=True)
            pdf.ln()
            pdf.set_font(font_name, "", 9)

        header_row()
        # 첫 칸이 이름(분류/우선순위)인 표만 왼쪽 정렬한다. 숫자뿐인 요약 표는 가운데다.
        name_col = first_col_ratio is not None
        for row in rows:
            if pdf.will_page_break(8):
                # 표가 페이지를 넘어가면 머리행을 다시 그린다. 없으면 숫자가 무슨 칸인지 모른다.
                pdf.add_page()
                header_row()
            for i, (v, w) in enumerate(zip(row, widths)):
                text = str(v)
                if i == 0 and name_col:
                    text = _fit(pdf, text, w - 2)
                pdf.cell(w, 8, text, border=1, align="L" if i == 0 and name_col else "C")
            pdf.ln()
        pdf.ln(6)

    def rate(v):
        return "-" if v is None else f"{v}%"

    # Title
    pdf.set_font(font_name, "B", 16)
    pdf.cell(0, 12, f"{project.name} - Test Report", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)

    # Run info
    pdf.set_font(font_name, "", 10)
    run_info = data["run"]
    pdf.cell(0, 7, f"Test Run: {run_info['name']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Version: {run_info.get('version') or 'N/A'}  |  Environment: {run_info.get('environment') or 'N/A'}  |  Round: {run_info['round']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 7, f"Status: {run_info['status']}  |  Created: {_fmt_dt(run_info.get('created_at'))}  |  Completed: {_fmt_dt(run_info.get('completed_at'))}", new_x="LMARGIN", new_y="NEXT")
    if data["executors"]:
        names = ", ".join(f"{e['name']} {e['count']}" for e in data["executors"])
        pdf.multi_cell(0, 7, f"Executed by: {names}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Summary
    heading("Summary")
    summary = data["summary"]
    table(
        ["Total", "Executed", "Pass", "Fail", "Block", "NA", "NS", "PASS Rate"],
        [[summary["total"], summary["executed"], summary["passed"], summary["failed"],
          summary["blocked"], summary["na"], summary["ns"], f"{summary['pass_rate']}%"]],
    )

    # 직전 수행 대비
    comp = data["comparison"]
    if comp:
        heading("Compared to Previous Run")
        pdf.set_font(font_name, "", 9)
        prev = comp["previous_run"]
        pdf.multi_cell(
            0, 6,
            f"Previous: {prev['name']} (R{prev['round']})  |  Executed in both: {comp['common']}  |  "
            f"Changed: {comp['changed']}  |  Regression (PASS->FAIL): {len(comp['regressions'])}  |  "
            f"Improved (FAIL->PASS): {len(comp['fixed'])}",
            new_x="LMARGIN", new_y="NEXT",
        )
        for label, items in (("Regression", comp["regressions"]), ("Improved", comp["fixed"])):
            if items:
                ids = ", ".join(i["tc_id"] or "-" for i in items)
                pdf.multi_cell(0, 6, f"{label}: {ids}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # Priority breakdown
    if data["priorities"]:
        heading("Priority Breakdown")
        table(
            ["Priority", "Total", "Pass", "Fail", "Block", "NA", "NS", "PASS Rate"],
            [[p["priority"] or UNSET_PRIORITY, p["total"], p["passed"], p["failed"], p["blocked"],
              p["na"], p["not_started"], rate(p["pass_rate"])] for p in data["priorities"]],
            first_col_ratio=0.22,
        )

    # Category breakdown
    if data["categories"]:
        heading("Category Breakdown")
        table(
            ["Category", "Total", "Pass", "Fail", "Block", "NA", "NS", "PASS Rate"],
            [[c["category"], c["total"], c["passed"], c["failed"], c["blocked"],
              c.get("na", 0), c.get("not_started", 0), rate(c["pass_rate"])] for c in data["categories"]],
            first_col_ratio=0.22,
        )

    # FAIL / BLOCK items
    if data["issue_items"]:
        heading("Failed / Blocked Test Cases")
        for idx, item in enumerate(data["issue_items"], 1):
            if pdf.will_page_break(7 + 5):
                pdf.add_page()
            pdf.set_font(font_name, "B", 9)
            path = " / ".join(x for x in (item.get("depth1"), item.get("depth2")) if x)
            head = f"{idx}. [{item['result']}] {item['tc_id']}"
            if item.get("priority"):
                head += f"  ({item['priority']})"
            if path:
                head += f"  {path}"
            pdf.multi_cell(0, 7, head, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font(font_name, "", 8)
            for label, key in (("Steps", "test_steps"), ("Expected", "expected_result"), ("Actual", "actual_result")):
                if item.get(key):
                    pdf.set_x(pdf.l_margin + 5)
                    pdf.multi_cell(pdf.epw - 5, 5, f"{label}: {_clip(item[key])}", new_x="LMARGIN", new_y="NEXT")
            if item.get("issue_link"):
                pdf.set_x(pdf.l_margin + 5)
                pdf.multi_cell(pdf.epw - 5, 5, f"Issue: {item['issue_link']}", new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

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
    ws_summary["B1"].value = safe_cell(f"{project.name} - Test Report")
    ws_summary["B1"].font = title_font

    run_info = data["run"]
    info_lines = [
        f"Test Run: {run.name}",
        f"Version: {run.version or 'N/A'}  |  Environment: {run.environment or 'N/A'}  |  Round: {run.round}",
        f"Status: {run_info['status']}  |  Created: {_fmt_dt(run_info['created_at'])}  |  Completed: {_fmt_dt(run_info['completed_at'])}",
    ]
    if data["executors"]:
        info_lines.append("Executed by: " + ", ".join(f"{e['name']} {e['count']}" for e in data["executors"]))
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
    row = write_table(
        row, "Summary",
        ["Total", "Executed", "Pass", "Fail", "Block", "NA", "NS", "PASS Rate"],
        [[summary["total"], summary["executed"], summary["passed"], summary["failed"],
          summary["blocked"], summary["na"], summary["ns"], summary["pass_rate"]]],
        rate_col=7,
    )

    comp = data["comparison"]
    if comp:
        prev = comp["previous_run"]
        row = write_table(
            row, safe_cell(f"Compared to Previous Run: {prev['name']} (R{prev['round']})"),
            ["Executed in both", "Changed", "Regression", "Improved"],
            [[comp["common"], comp["changed"], len(comp["regressions"]), len(comp["fixed"])]],
        )
        for label, items in (("Regression (PASS->FAIL)", comp["regressions"]), ("Improved (FAIL->PASS)", comp["fixed"])):
            if items:
                ids = ", ".join(i["tc_id"] or "-" for i in items)
                ws_summary.cell(row=row - 1, column=2, value=safe_cell(f"{label}: {ids}")).font = cell_font
                row += 1
        row += 1

    if data["priorities"]:
        row = write_table(
            row, "Priority Breakdown",
            ["Priority", "Total", "Pass", "Fail", "Block", "NA", "NS", "PASS Rate"],
            [[p["priority"] or UNSET_PRIORITY, p["total"], p["passed"], p["failed"], p["blocked"],
              p["na"], p["not_started"], p["pass_rate"]] for p in data["priorities"]],
            rate_col=7,
        )

    if data["categories"]:
        row = write_table(
            row, "Category Breakdown",
            ["Category", "Total", "Pass", "Fail", "Block", "NA", "NS", "PASS Rate"],
            [[c["category"], c["total"], c["passed"], c["failed"], c["blocked"],
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
