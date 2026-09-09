"""시트 안에서 no 는 1 부터 이어지고 겹치지 않는다.

마이그레이션으로 한 번 정리해도, 번호를 넣는 경로가 그대로면 다시 어긋난다.
TC 를 만드는 길은 넷이다: 신규 생성, 복제, 엑셀 임포트, 드래그 정렬.
넷 다 규약을 지키는지 본다.

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_tc_no_contract.py -v
"""
import io
import os

import pytest
import requests
from openpyxl import Workbook

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

import dev_db_guard

if dev_db_guard.DEV_DB_AT_RISK:
    pytest.skip(dev_db_guard.SKIP_REASON, allow_module_level=True)


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture
def project(token):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__no_contract__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    for sheet in ("로그인", "결제"):
        rs = requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                           json={"name": sheet, "parent_id": None, "is_folder": False})
        assert rs.status_code in (200, 201), rs.text
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _add(token, pid, sheet, tc_id, no=None):
    body = {
        "tc_id": tc_id, "test_steps": "1. 실행", "expected_result": "성공",
        "sheet_name": sheet, "priority": "High",
    }
    if no is not None:
        body["no"] = no
    return requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json=body)


def _nos(token, pid, sheet):
    r = requests.get(f"{BASE}/api/projects/{pid}/testcases",
                     headers=auth(token), params={"sheet_name": sheet})
    assert r.status_code == 200, r.text
    return sorted(tc["no"] for tc in r.json())


def _assert_contract(token, pid, sheet, expected=None):
    """시트 안 번호가 1..N 인지 본다.

    expected 를 주면 건수도 함께 본다. 빈 시트는 규약을 저절로 만족하므로,
    임포트가 아무것도 넣지 못한 경우가 통과로 보이는 것을 막는다.
    """
    nos = _nos(token, pid, sheet)
    if expected is not None:
        assert len(nos) == expected, f"{sheet}: {expected}건이어야 하는데 {len(nos)}건"
    assert nos == list(range(1, len(nos) + 1)), f"{sheet}: 1..N 이 아니다 -> {nos}"


def test_new_rows_are_numbered_by_server(token, project):
    """신규 생성은 서버가 그 시트의 다음 번호를 준다."""
    for i in range(1, 4):
        r = _add(token, project, "결제", f"TC-{i:03d}")
        assert r.status_code == 201, r.text
        assert r.json()["no"] == i

    _assert_contract(token, project, "결제")


def test_client_supplied_number_cannot_break_contract(token, project):
    """클라이언트가 엉뚱한 번호를 보내도 규약이 깨지지 않는다."""
    assert _add(token, project, "결제", "TC-001").status_code == 201
    r = _add(token, project, "결제", "TC-002", no=999)
    assert r.status_code == 201, r.text

    _assert_contract(token, project, "결제")


def test_duplicate_number_is_ignored_not_stored(token, project):
    """이미 쓰이는 번호를 보내도 그 값이 저장되지 않는다."""
    assert _add(token, project, "결제", "TC-001").status_code == 201
    r = _add(token, project, "결제", "TC-002", no=1)

    assert r.status_code == 201, r.text
    assert r.json()["no"] == 2, "보낸 1 이 아니라 서버가 정한 2 여야 한다"
    _assert_contract(token, project, "결제")


def test_sheets_are_numbered_separately(token, project):
    """시트가 다르면 같은 번호를 쓴다."""
    assert _add(token, project, "로그인", "TC-L1").status_code == 201
    assert _add(token, project, "결제", "TC-P1").status_code == 201

    assert _nos(token, project, "로그인") == [1]
    assert _nos(token, project, "결제") == [1]


def test_reorder_can_swap_numbers(token, project):
    """드래그 정렬이 번호를 맞바꿔도 중간에 겹치지 않는다."""
    h = auth(token)
    ids = []
    for i in range(1, 4):
        r = _add(token, project, "결제", f"TC-{i:03d}")
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])

    # 완전히 뒤집는다. 한 건씩 갱신하면 중간 상태에서 반드시 번호가 겹친다.
    payload = {"items": [{"id": tc, "no": n} for tc, n in zip(reversed(ids), [1, 2, 3])]}
    r = requests.put(f"{BASE}/api/projects/{project}/testcases/reorder", headers=h, json=payload)

    assert r.status_code == 200, r.text
    _assert_contract(token, project, "결제")
    got = requests.get(f"{BASE}/api/projects/{project}/testcases",
                       headers=h, params={"sheet_name": "결제"}).json()
    assert [tc["id"] for tc in sorted(got, key=lambda t: t["no"])] == list(reversed(ids))


def test_reorder_refuses_partial_sheet(token, project):
    """시트의 일부만 보내는 정렬은 거절한다.

    화면에서 필터를 걸면 보이는 행만 1..k 를 받는다. 그대로 저장하면 숨은 행과
    번호가 겹친다. 화면 표시값이 DB 로 새는 자리다.
    """
    h = auth(token)
    ids = [_add(token, project, "결제", f"TC-{i:03d}").json()["id"] for i in range(1, 4)]

    payload = {"items": [{"id": ids[0], "no": 1}, {"id": ids[1], "no": 2}]}
    r = requests.put(f"{BASE}/api/projects/{project}/testcases/reorder", headers=h, json=payload)

    assert r.status_code == 400, r.text
    _assert_contract(token, project, "결제")


def test_reorder_refuses_mixed_sheets(token, project):
    """시트를 넘나드는 정렬은 거절한다.

    전체 보기 화면은 시트 경계를 넘는 연번을 그린다. 그 상태로 드래그하면 시트
    전체에 걸친 1..N 이 저장돼 시트 안 규약이 한 번에 무너진다.
    """
    h = auth(token)
    a = _add(token, project, "로그인", "TC-L1").json()["id"]
    b = _add(token, project, "결제", "TC-P1").json()["id"]

    payload = {"items": [{"id": a, "no": 1}, {"id": b, "no": 2}]}
    r = requests.put(f"{BASE}/api/projects/{project}/testcases/reorder", headers=h, json=payload)

    assert r.status_code == 400, r.text
    assert _nos(token, project, "로그인") == [1]
    assert _nos(token, project, "결제") == [1]


def test_reorder_refuses_numbers_that_are_not_one_to_n(token, project):
    """1..N 이 아닌 번호는 거절한다."""
    h = auth(token)
    ids = [_add(token, project, "결제", f"TC-{i:03d}").json()["id"] for i in range(1, 4)]

    payload = {"items": [{"id": t, "no": n} for t, n in zip(ids, [1, 2, 7])]}
    r = requests.put(f"{BASE}/api/projects/{project}/testcases/reorder", headers=h, json=payload)

    assert r.status_code == 400, r.text
    _assert_contract(token, project, "결제")


def _excel(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "결제"
    ws.append(["No", "TC ID", "Test Script (Step-by-Step) - Step", "Expected Result"])
    for no, tc_id in rows:
        ws.append([no, tc_id, "1. 실행", "성공"])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_import_numbers_are_normalized(token, project):
    """엑셀의 No 가 띄엄띄엄해도 들어온 뒤에는 1..N 이다."""
    files = {"file": ("t.xlsx", _excel([(10, "TC-A"), (20, "TC-B"), (30, "TC-C")]),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)
    assert r.status_code in (200, 201), r.text

    _assert_contract(token, project, "결제")


def test_import_keeps_row_order(token, project):
    """번호를 다시 매기더라도 엑셀에 적힌 차례는 지킨다."""
    files = {"file": ("t.xlsx", _excel([(30, "TC-A"), (10, "TC-B"), (20, "TC-C")]),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)
    assert r.status_code in (200, 201), r.text

    got = requests.get(f"{BASE}/api/projects/{project}/testcases",
                       headers=auth(token), params={"sheet_name": "결제"}).json()
    assert [tc["tc_id"] for tc in sorted(got, key=lambda t: t["no"])] == ["TC-A", "TC-B", "TC-C"]


def test_update_cannot_change_number(token, project):
    """수정 API 로 번호를 바꿀 수 없다.

    번호는 순번이라 사람이 직접 정할 값이 아니다. 열어 두면 구멍이 생기거나
    유니크 제약에 걸려 409 가 난다.
    """
    h = auth(token)
    ids = [_add(token, project, "결제", f"TC-{i:03d}").json()["id"] for i in range(1, 4)]

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/{ids[0]}",
                     headers=h, json={"no": 99})

    assert r.status_code == 200, r.text
    assert r.json()["no"] == 1, "보낸 번호가 저장되면 안 된다"
    _assert_contract(token, project, "결제")


def test_bulk_update_cannot_change_number(token, project):
    """일괄 수정도 마찬가지다."""
    h = auth(token)
    ids = [_add(token, project, "결제", f"TC-{i:03d}").json()["id"] for i in range(1, 4)]

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/bulk", headers=h,
                     json={"items": [{"id": ids[0], "no": 50}, {"id": ids[1], "no": 60}]})

    assert r.status_code == 200, r.text
    _assert_contract(token, project, "결제")


def test_moving_to_another_sheet_renumbers_both(token, project):
    """시트를 옮기면 떠난 시트와 도착한 시트가 모두 1..N 이 된다."""
    h = auth(token)
    ids = [_add(token, project, "결제", f"TC-P{i}").json()["id"] for i in range(1, 4)]
    _add(token, project, "로그인", "TC-L1")

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/{ids[1]}",
                     headers=h, json={"sheet_name": "로그인"})

    assert r.status_code == 200, r.text
    _assert_contract(token, project, "결제")
    _assert_contract(token, project, "로그인")
    assert len(_nos(token, project, "결제")) == 2
    assert len(_nos(token, project, "로그인")) == 2


NL = chr(10)


def _csv_bytes(rows):
    head = "No,TC ID,Test Script (Step-by-Step) - Step,Expected Result" + NL
    body = "".join(f"{no},{tc},1. 실행,성공" + NL for no, tc in rows)
    return io.BytesIO((head + body).encode("utf-8-sig"))


def test_csv_import_numbers_are_normalized(token, project):
    """CSV 임포트도 엑셀과 같은 규약을 지킨다.

    CSV 는 시트 이름을 고를 수 없고 "CSV Import" 로 들어간다.
    """
    files = {"file": ("t.csv", _csv_bytes([(10, "TC-A"), (20, "TC-B")]), "text/csv")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)
    assert r.status_code in (200, 201), r.text
    assert r.json()["imported"] == 2, r.text

    _assert_contract(token, project, "CSV Import", expected=2)


def _md_bytes(rows):
    head = "| No | TC ID | Test Script (Step-by-Step) - Step | Expected Result |" + NL
    sep = "| --- | --- | --- | --- |" + NL
    body = "".join(f"| {no} | {tc} | 1. 실행 | 성공 |" + NL for no, tc in rows)
    return io.BytesIO((head + sep + body).encode("utf-8"))


def test_markdown_import_numbers_are_normalized(token, project):
    """마크다운 임포트도 같은 규약을 지킨다.

    시트 이름은 표 제목에서 온다. 응답이 알려 주는 이름으로 확인한다.
    """
    files = {"file": ("t.md", _md_bytes([(10, "TC-A"), (20, "TC-B")]), "text/markdown")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["imported"] == 2, body
    sheet = body["sheets"][0]["sheet"]

    _assert_contract(token, project, sheet, expected=2)


def test_import_into_sheet_that_already_has_tcs(token, project):
    """TC 가 이미 있는 시트에 임포트해도 실패하지 않는다.

    파일은 행에 1..N 을 붙여 들어온다. 그 시트에 이미 1..N 이 있으면 넣는 도중
    번호가 겹친다. 유니크 제약을 건 뒤로는 그 자리에서 터진다.
    """
    for i in range(1, 4):
        assert _add(token, project, "결제", f"TC-OLD-{i}").status_code == 201

    files = {"file": ("t.xlsx", _excel([(1, "TC-NEW")]),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)

    assert r.status_code in (200, 201), r.text
    _assert_contract(token, project, "결제", expected=4)


def test_import_can_reverse_existing_rows(token, project):
    """기존 행을 역순으로 담은 파일을 임포트해도 실패하지 않는다.

    기존 행끼리 자리를 맞바꾸는 경우다. 한 건씩 갱신하면 중간에 반드시 겹친다.
    """
    ids = [_add(token, project, "결제", f"TC-{i}").json()["id"] for i in (1, 2, 3)]
    assert len(ids) == 3

    files = {"file": ("t.xlsx", _excel([(1, "TC-3"), (2, "TC-2"), (3, "TC-1")]),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)

    assert r.status_code in (200, 201), r.text
    _assert_contract(token, project, "결제", expected=3)
    got = requests.get(f"{BASE}/api/projects/{project}/testcases",
                       headers=auth(token), params={"sheet_name": "결제"}).json()
    assert [t["tc_id"] for t in sorted(got, key=lambda x: x["no"])] == ["TC-3", "TC-2", "TC-1"]


def test_csv_import_rejects_negative_numbers(token, project):
    """파일에 음수 번호가 있어도 저장되지 않는다.

    번호를 옮길 때 쓰는 임시 자리가 음수다. 음수가 실제 데이터로 들어오면 그
    자리와 부딪친다.
    """
    # ★파일의 No 는 저장되지 않으므로 어떤 값이 와도 1..N 이어야 한다. 음수를
    #   실제로 다루는 것은 park/renumber 쪽이고 그쪽은 test_tc_renumber_service.py
    #   가 본다.
    files = {"file": ("t.csv", _csv_bytes([(-5, "TC-N1"), (-1000001, "TC-N2")]), "text/csv")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)
    assert r.status_code in (200, 201), r.text
    assert r.json()["imported"] == 2, r.text

    _assert_contract(token, project, "CSV Import", expected=2)
    got = requests.get(f"{BASE}/api/projects/{project}/testcases",
                       headers=auth(token), params={"sheet_name": "CSV Import"}).json()
    assert [t["tc_id"] for t in sorted(got, key=lambda x: x["no"])] == ["TC-N1", "TC-N2"],         "파일에 적힌 차례를 지켜야 한다"


def test_markdown_import_rejects_negative_numbers(token, project):
    """마크다운도 마찬가지다."""
    files = {"file": ("t.md", _md_bytes([(-3, "TC-N1"), (-9, "TC-N2")]), "text/markdown")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["imported"] == 2, body

    _assert_contract(token, project, body["sheets"][0]["sheet"], expected=2)


def test_import_twice_into_same_sheet(token, project):
    """같은 파일을 두 번 임포트해도 규약이 유지된다.

    두 번째에는 기존 행이 이미 비켜 둔 자리를 거쳐 간다.
    """
    files = lambda: {"file": ("t.xlsx", _excel([(1, "TC-A"), (2, "TC-B")]),
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    for _ in range(2):
        r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                          headers=auth(token), files=files())
        assert r.status_code in (200, 201), r.text

    _assert_contract(token, project, "결제", expected=2)


def test_import_file_with_duplicate_numbers(token, project):
    """파일 안에 같은 번호가 두 번 있어도 받아들인다.

    사람이 만든 엑셀에서 흔하다. 파일의 번호를 그대로 저장하면 넣는 도중에 겹친다.
    """
    files = {"file": ("t.xlsx", _excel([(1, "TC-A"), (1, "TC-B"), (2, "TC-C")]),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)

    assert r.status_code in (200, 201), r.text
    _assert_contract(token, project, "결제", expected=3)


def test_csv_import_file_with_duplicate_numbers(token, project):
    """CSV 도 마찬가지다."""
    files = {"file": ("t.csv", _csv_bytes([(1, "TC-A"), (1, "TC-B")]), "text/csv")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)

    assert r.status_code in (200, 201), r.text
    _assert_contract(token, project, "CSV Import", expected=2)


def test_markdown_import_file_with_duplicate_numbers(token, project):
    """마크다운 파일 안에 같은 번호가 두 번 있어도 받아들인다."""
    files = {"file": ("t.md", _md_bytes([(1, "TC-A"), (1, "TC-B")]), "text/markdown")}
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                      headers=auth(token), files=files)

    assert r.status_code in (200, 201), r.text
    body = r.json()
    _assert_contract(token, project, body["sheets"][0]["sheet"], expected=2)
