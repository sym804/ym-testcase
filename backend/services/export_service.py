import io
from urllib.parse import quote

from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from services.excel_safe import safe_cell as _sanitize_cell
from services.precondition_service import build_index, expand_text, has_ref


# 헤더에서 Precondition 이 몇 번째 열인지 (values 리스트 기준 0-based)
PRECONDITION_OFFSET = 8



#: 엑셀 시트명 상한. 넘기면 엑셀이 파일을 복구 대상으로 본다.
SHEET_TITLE_LIMIT = 31


def _safe_sheet_title(name: str, used: set) -> str:
    """엑셀이 받는 시트명으로 바꾼다. 31자 이하, 금지 문자 없음, 중복 없음.

    자르기를 정제보다 먼저 하면 안 된다. 31자까지 같은 이름 둘은 잘린 뒤 충돌하는데,
    openpyxl 은 중복을 만나면 뒤에 번호를 붙인다. 그 번호가 상한 밖으로 나가 32자짜리
    탭이 생긴다(실측). 여기서 번호까지 포함해 상한 안에 넣는다.
    """
    safe = name or ""
    for ch in "/\\":
        safe = safe.replace(ch, "-")
    for ch in "*?[]:":
        safe = safe.replace(ch, "")
    safe = safe.strip() or "기본"
    safe = safe[:SHEET_TITLE_LIMIT]

    if safe not in used:
        used.add(safe)
        return safe

    for i in range(2, 1000):
        suffix = f"_{i}"
        candidate = safe[: SHEET_TITLE_LIMIT - len(suffix)] + suffix
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise ValueError(f"시트명 중복을 풀지 못했다: {name}")

def export_testcases_excel(
    project, testcases, split_sheets: bool, expand_refs: bool = False
) -> StreamingResponse:
    """TC 목록을 Excel 파일로 생성하여 StreamingResponse로 반환한다.

    사전조건이 다른 TC 를 참조하는 경우(예: "REC-API-01 의 사전조건 1~4 참조"),
    엑셀에서는 앱의 호버 팝업이 없어 참조가 읽히지 않는다. 두 가지로 보완한다.

    - expand_refs=False (기본): 참조 문구는 그대로 두고, 펼친 사전조건을 셀 메모로 단다.
    - expand_refs=True: 참조를 펼친 전문으로 바꿔 쓴다. 메모를 못 읽는 도구용.

    색인은 프로젝트 전체 TC 로 만든다. 시트 분리 시에도 참조를 따라갈 수 있어야 한다.
    """
    index = build_index(testcases)
    wb = Workbook()

    # -- Styles --
    dark_fill = PatternFill(start_color="2F3136", end_color="2F3136", fill_type="solid")
    header_font = Font(name="Malgun Gothic", bold=True, color="FFFFFF", size=10)
    cell_font = Font(name="Malgun Gothic", size=10)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    pass_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    fail_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    block_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    na_fill = PatternFill(start_color="D9D9D9", end_color="D9D9D9", fill_type="solid")

    headers = [
        "No", "TC ID", "Type", "Category", "Depth1", "Depth2",
        "Priority", "Platform", "Precondition", "Steps",
        "Expected Result", "Remarks",
        "Result", "Actual Result", "Issue Link", "Remarks (Run)",
    ]
    col_widths = [6, 10, 10, 15, 18, 18, 10, 12, 25, 35, 35, 20, 10, 35, 20, 20]

    def _write_sheet(ws, sheet_title, tcs, show_title=True):
        """시트 하나에 TC 목록을 쓴다."""
        if show_title:
            max_col_letter = get_column_letter(len(headers) + 1)
            ws.merge_cells(f"B1:{max_col_letter}1")
            title_cell = ws["B1"]
            title_cell.value = _sanitize_cell(f"{project.name} - {sheet_title}")
            title_cell.font = Font(name="Malgun Gothic", bold=True, size=14)
            title_cell.alignment = Alignment(horizontal="center", vertical="center")

            ws.merge_cells(f"B3:{max_col_letter}3")
            ws["B3"].value = f"Project: {project.name}"
            ws["B3"].font = Font(name="Malgun Gothic", size=10)

        for idx, (header, width) in enumerate(zip(headers, col_widths)):
            col = idx + 2
            cell = ws.cell(row=5, column=col, value=header)
            cell.font = header_font
            cell.fill = dark_fill
            cell.alignment = center_align
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col)].width = width

        for row_offset, tc in enumerate(tcs):
            row = 6 + row_offset
            values = [
                tc.no, tc.tc_id, tc.type, tc.category, tc.depth1, tc.depth2,
                tc.priority, tc.test_type, tc.precondition, tc.test_steps,
                tc.expected_result, tc.remarks,
                "", "", "", "",
            ]
            for col_offset, value in enumerate(values):
                col = col_offset + 2
                is_precondition = col_offset == PRECONDITION_OFFSET and has_ref(tc.precondition)
                if is_precondition and expand_refs:
                    value = expand_text(tc.tc_id, index)
                cell = ws.cell(row=row, column=col, value=_sanitize_cell(value))
                cell.font = cell_font
                cell.border = thin_border
                if is_precondition and not expand_refs:
                    note = "펼친 사전조건\n" + expand_text(tc.tc_id, index)
                    comment = Comment(note, "TC Manager")
                    comment.width = 420
                    comment.height = 30 + 18 * (note.count("\n") + 1)
                    cell.comment = comment
                if col_offset < 2 or col_offset == 6 or col_offset == 7 or col_offset == 12 or col_offset == 14:
                    cell.alignment = center_align
                else:
                    cell.alignment = left_align

        result_col = 14 + 2  # Result column
        for row in range(6, 6 + len(tcs)):
            cell = ws.cell(row=row, column=result_col)
            val = str(cell.value or "").upper()
            if val == "PASS":
                cell.fill = pass_fill
            elif val == "FAIL":
                cell.fill = fail_fill
            elif val == "BLOCK":
                cell.fill = block_fill
            elif val in ("NA", "N/A"):
                cell.fill = na_fill

        ws.freeze_panes = "B6"

    if split_sheets:
        # 시트별 분리: sheet_name 기준으로 엑셀 탭 생성
        from collections import OrderedDict
        sheets_map: OrderedDict[str, list] = OrderedDict()
        for tc in testcases:
            name = tc.sheet_name or "기본"
            sheets_map.setdefault(name, []).append(tc)

        if not sheets_map:
            # TC 가 0건이면 만들 탭이 없다. 기본 시트를 지우면 워크북에 시트가 하나도
            # 남지 않아 저장이 IndexError 로 죽는다. 통합 모드와 같은 헤더 시트를 둔다.
            sheets_map["Test Cases"] = []

        wb.remove(wb.active)  # 기본 빈 시트 제거
        used_titles: set[str] = set()
        for sheet_name, tcs in sheets_map.items():
            ws = wb.create_sheet(title=_safe_sheet_title(sheet_name, used_titles))
            _write_sheet(ws, sheet_name, tcs)
    else:
        # 통합: 단일 시트
        ws = wb.active
        ws.title = "Test Cases"
        _write_sheet(ws, "Test Cases", testcases)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return _xlsx_response(output, project)


def _xlsx_response(output, project) -> StreamingResponse:
    filename = f"{project.name}_TestCases.xlsx"
    encoded = quote(filename)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
