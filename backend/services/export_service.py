import io
from urllib.parse import quote

from fastapi.responses import StreamingResponse

from services.excel_safe import safe_cell as _sanitize_cell
from services.precondition_service import build_index, expand_text, has_ref


# 헤더에서 Precondition 이 몇 번째 열인지 (values 리스트 기준 0-based)
PRECONDITION_OFFSET = 8



#: 엑셀 시트명 상한. 넘기면 엑셀이 파일을 복구 대상으로 본다.
SHEET_TITLE_LIMIT = 31


def _safe_sheet_title(name: str, used: set) -> str:
    """엑셀이 받는 시트명으로 변경한다. 31자 이하, 금지 문자 없음, 중복 없음.

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

    사전조건이 다른 TC 를 참조하는 경우(예: "ORD-API-01 의 사전조건 1~4 참조"),
    엑셀에서는 앱의 호버 팝업이 없어 참조가 읽히지 않는다. 두 가지로 보완한다.

    - expand_refs=False (기본): 참조 문구는 그대로 두고, 펼친 사전조건을 셀 메모로 단다.
    - expand_refs=True: 참조를 펼친 전문으로 변경해 쓴다. 메모를 못 읽는 도구용.

    색인은 프로젝트 전체 TC 로 만든다. 시트 분리 시에도 참조를 따라갈 수 있어야 한다.
    """
    # openpyxl 은 이 함수에서만 쓴다. 모듈 최상단에서 올리면 콜드 스타트마다 임포트 비용을 낸다.
    from openpyxl import Workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

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


#: Markdown 표 열. 머리글 이름은 Markdown 가져오기(map_header)가 읽는 이름과 같아야
#: 내보낸 파일을 다시 가져올 수 있다. 엑셀의 수행 결과 빈 열 4개는 표만 넓혀서 뺀다.
MD_COLUMNS = [
    ("No", "no"), ("TC ID", "tc_id"), ("Type", "type"), ("Category", "category"),
    ("Depth1", "depth1"), ("Depth2", "depth2"), ("Priority", "priority"),
    ("Platform", "test_type"), ("Precondition", "precondition"), ("Steps", "test_steps"),
    ("Expected Result", "expected_result"), ("Remarks", "remarks"),
]


def _md_cell(value) -> str:
    """값 하나를 표 칸 안에 들어가는 한 줄로 바꾼다.

    가져오기 파서는 `\\|` 를 파이프로, `<br>` 을 줄바꿈으로, `&lt;` `&gt;` `&amp;` 를
    글자로 되돌린다. 그 역순으로 쓴다.

    - `&` 와 `<` 를 엔티티로 쓴다. 원문에 `<br>` 이라는 글자가 있으면 줄바꿈과 구별할 수
      없어서다. 웹 TC 에는 "<br> 태그가 렌더된다" 같은 문장이 실제로 나온다.
      `&` 까지 바꿔야 원문 `&lt;` 가 `<` 로 둔갑하지 않는다.
    - 역슬래시는 따로 이스케이프하지 않아도 된다. 원문 `a\\|b` 는 `a\\\\|b` 로 나가고,
      파서가 뒤쪽 `\\|` 만 파이프로 바꿔 `a\\|b` 로 돌아온다.
    """
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("&", "&amp;").replace("<", "&lt;")
    return text.replace("|", "\\|").replace("\n", "<br>")


def _md_heading(name: str) -> str:
    """시트·프로젝트 이름을 헤딩 한 줄로 쓴다. 이름 속 줄바꿈은 헤딩을 쪼개거나 표를 끼워 넣으므로 공백으로 바꾼다."""
    return " ".join(str(name).splitlines()).strip() or "기본"


def _md_table(tcs, index, expand_refs: bool) -> list[str]:
    lines = [
        "| " + " | ".join(h for h, _ in MD_COLUMNS) + " |",
        "|" + "|".join("---" for _ in MD_COLUMNS) + "|",
    ]
    for tc in tcs:
        cells = []
        for _, field in MD_COLUMNS:
            value = getattr(tc, field)
            if field == "precondition" and expand_refs and has_ref(value):
                value = expand_text(tc.tc_id, index)
            cells.append(_md_cell(value))
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def build_testcases_markdown(project, testcases, split_sheets: bool, expand_refs: bool = False) -> str:
    """TC 목록을 Markdown 문서로 만든다. 가져오기는 표 바로 위 헤딩을 시트 이름으로 쓴다.

    - split_sheets=False: `## Test Cases` 아래 표 하나. 엑셀 통합 모드의 시트 이름과 같다.
    - split_sheets=True: 시트마다 `## <시트 이름>` 과 표. 차례는 받은 목록 그대로다.
      다시 가져왔을 때 시트 구성이 유지되는 것은 이 모드뿐이다. 통합 모드는 엑셀과
      같이 전부 `Test Cases` 시트로 들어간다.

    엑셀은 참조를 펼친 사전조건을 셀 메모로 달지만 Markdown 에는 메모가 없다.
    expand_refs=False 면 참조 문구를 그대로 두고, True 면 펼친 전문으로 바꾼다.
    """
    index = build_index(testcases)
    lines = [f"# {_md_heading(project.name)}", ""]
    if split_sheets:
        groups: dict[str, list] = {}
        for tc in testcases:
            groups.setdefault(tc.sheet_name or "기본", []).append(tc)
        if not groups:
            groups["Test Cases"] = []
    else:
        groups = {"Test Cases": list(testcases)}

    for name, tcs in groups.items():
        lines += [f"## {_md_heading(name)}", ""]
        lines += _md_table(tcs, index, expand_refs)
        lines.append("")
    return "\n".join(lines)


def export_testcases_markdown(
    project, testcases, split_sheets: bool, expand_refs: bool = False
) -> StreamingResponse:
    body = build_testcases_markdown(project, testcases, split_sheets, expand_refs).encode("utf-8")
    encoded = quote(f"{project.name}_TestCases.md")
    return StreamingResponse(
        io.BytesIO(body),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )


def _xlsx_response(output, project) -> StreamingResponse:
    filename = f"{project.name}_TestCases.xlsx"
    encoded = quote(filename)
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded}"},
    )
