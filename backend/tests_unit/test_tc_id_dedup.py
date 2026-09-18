"""TC ID 채번과 임포트 중복 처리

TC ID 는 프로젝트 안에서 유일해야 한다. 사전조건 참조 색인이 프로젝트 전체
TC 로 만들어져서, 같은 ID 가 둘이면 참조가 어느 쪽을 가리키는지 정해지지 않는다.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, Project, TestCase, TestCaseSheet, User
from services.import_service import _parse_csv, _parse_md_table, _parse_md_tables, _parse_sheet
from services.tc_id_service import TC_ID_MAX_LEN, allocate_tc_id


# ── allocate_tc_id ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("base,taken,want", [
    ("SFW-001", {"SFW-002"}, "SFW-001"),
    ("SFW-001", {"SFW-001"}, "SFW-001-2"),
    ("SFW-001", {"SFW-001", "SFW-001-2"}, "SFW-001-3"),
    ("TC-5-copy", {"TC-5", "TC-5-copy"}, "TC-5-copy-2"),
    ("", set(), "TC"),
    ("   ", set(), "TC"),
])
def test_allocate_tc_id(base, taken, want):
    assert allocate_tc_id(base, taken) == want


def test_길이_상한을_넘지_않는다():
    """String(50) 이라 잘라야 하는데, 자른 결과가 기존 ID 와 같으면 안 된다."""
    long_base = "X" * 60
    fitted = long_base[:TC_ID_MAX_LEN]
    got = allocate_tc_id(long_base, {fitted})
    assert len(got) <= TC_ID_MAX_LEN
    assert got != fitted
    assert allocate_tc_id(long_base, {fitted, got}) not in {fitted, got}


def test_같은_루프에서_연달아_채번한다():
    """임포트는 결과를 taken 에 넣어 가며 돈다."""
    taken = {"A-1"}
    got = []
    for _ in range(3):
        new_id = allocate_tc_id("A-1", taken)
        taken.add(new_id)
        got.append(new_id)
    assert got == ["A-1-2", "A-1-3", "A-1-4"]


# ── 임포트 ────────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path):
    db_path = str(tmp_path / "probe.db").replace("\\", "/")
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, username="u", password_hash="x", display_name="u", role="admin"))
    session.add(Project(id=1, name="P", created_by=1))
    session.add(TestCaseSheet(project_id=1, name="S1", sort_order=0))
    session.add(TestCaseSheet(project_id=1, name="S2", sort_order=1))
    session.commit()
    yield session
    session.close()


def _sheet(title, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = title
    ws.append(["No", "TC ID", "Test Steps", "Expected Result"])
    for r in rows:
        ws.append(r)
    return ws


def _ids(db, sheet_name=None):
    q = db.query(TestCase.tc_id).filter(
        TestCase.project_id == 1, TestCase.deleted_at.is_(None)
    )
    if sheet_name:
        q = q.filter(TestCase.sheet_name == sheet_name)
    return sorted(r[0] for r in q.all())


def _import(db, sheet_name, rows):
    r = _parse_sheet(_sheet(sheet_name, rows), 1, 1, db, no_offset=0, sheet_name=sheet_name)
    db.commit()
    return r


def test_한_파일_안의_중복은_번호를_붙여_넣는다(db):
    r = _import(db, "S1", [[1, "A-001", "s", "e"], [2, "A-001", "s2", "e2"], [3, "A-002", "s3", "e3"]])
    assert (r["created"], r["renamed"]) == (3, 1)
    assert _ids(db, "S1") == ["A-001", "A-001-2", "A-002"]


def test_TC_ID_가_비고_no_가_전부_같아도_겹치지_않는다(db):
    """대량 행 추가 버그가 만들어 낸 파일 모양. 예전에는 TC-001 이 세 건 생겼다."""
    r = _import(db, "S2", [[1, "", "s", "e"], [1, "", "s", "e"], [1, "", "s", "e"]])
    # ★renamed 는 2 그대로다. 접미사를 붙이는 주체가 채번에서 파서로 바뀌었을 뿐
    #   (SYM-51), 사용자에게는 여전히 "번호를 붙여 넣었다" 고 알려야 한다.
    assert (r["created"], r["renamed"]) == (3, 2)
    assert _ids(db, "S2") == ["TC-001", "TC-001-2", "TC-001-3"]


def test_다른_시트에_있는_ID_와도_겹치지_않는다(db):
    """existing_map 은 시트 단위지만 유일성은 프로젝트 단위다."""
    _import(db, "S1", [[1, "A-001", "s", "e"]])
    r = _import(db, "S2", [[9, "A-001", "s", "e"]])
    assert (r["created"], r["renamed"]) == (1, 1)
    assert "A-001" not in _ids(db, "S2")
    assert _ids(db, "S2") == ["A-001-2"]


def test_같은_시트_재임포트는_갱신이다(db):
    """중복 회피가 덮어쓰기 동작을 밀어내지 않아야 한다."""
    _import(db, "S1", [[1, "A-001", "old", "e"]])
    before = _ids(db)
    r = _import(db, "S1", [[1, "A-001", "new", "e"]])
    assert (r["created"], r["updated"]) == (0, 1)
    assert _ids(db) == before
    row = db.query(TestCase).filter(TestCase.tc_id == "A-001").one()
    assert row.test_steps == "new"


def test_임포트_후_프로젝트_전체_ID_가_유일하다(db):
    _import(db, "S1", [[1, "A-001", "s", "e"], [2, "A-001", "s", "e"]])
    _import(db, "S2", [[1, "", "s", "e"], [1, "", "s", "e"], [3, "A-001", "s", "e"]])
    ids = _ids(db)
    assert len(ids) == len(set(ids))


# ── 재임포트로 내용을 갱신하는 흐름 (SYM-51) ─────────────────────────────────
# 이 앱의 임포트 계약은 "동일한 TC ID 는 덮어쓰기" 다(화면 안내 문구).
# TC ID 칸이 비면 파일의 No 로 ID 를 만들어 그 계약에 태운다. 그래서 파일 안에
# 같은 No 가 두 번 나오면 두 행이 한 기존 행을 덮으려 들었다.

def _steps(db, sheet_name):
    q = db.query(TestCase.tc_id, TestCase.test_steps).filter(
        TestCase.project_id == 1,
        TestCase.sheet_name == sheet_name,
        TestCase.deleted_at.is_(None),
    )
    return {tid: steps for tid, steps in q.all()}


def test_No_가_겹치는_파일을_다시_넣어도_각_행이_제_자리에_갱신된다(db):
    """SYM-51 본체. 예전에는 두 행이 모두 TC-001 을 찾아 앞 행을 두 번 덮었다.
    뒤 행의 내용은 영영 반영되지 않는데 결과는 updated 2 로 보고된다.

    ★단위 테스트만 보면 IntegrityError 가 나서 그것이 증상인 줄 알았는데 아니다.
      라우트는 _parse_sheet 앞에 park_sheet_numbers 로 기존 번호를 음수로 비켜
      두므로 실제 앱에서는 유니크 제약에 안 걸린다. 조용히 덮어쓰는 쪽이 에러보다
      나쁘다. 아래 test_라우트_차례로도_제_자리에_갱신된다 가 그 경로를 태운다.
    """
    first = _import(db, "S1", [[1, "", "s1", "e"], [1, "", "s2", "e"]])
    assert (first["created"], first["updated"]) == (2, 0)
    assert _steps(db, "S1") == {"TC-001": "s1", "TC-001-2": "s2"}

    second = _import(db, "S1", [[1, "", "s1x", "e"], [1, "", "s2x", "e"]])

    assert (second["created"], second["updated"]) == (0, 2), "기존 행을 못 찾았다"
    assert _steps(db, "S1") == {"TC-001": "s1x", "TC-001-2": "s2x"}


def test_만들어지는_ID_는_예전과_같다(db):
    """★호환성의 핵심. ID 생성 규칙을 바꾸면 이미 임포트해 둔 데이터를 재임포트가
    못 찾아 새 행을 만들고, 그것도 no 유니크 제약에 걸린다. 파일 No 기반이라는
    규칙은 그대로 두고, 파일 안 중복만 파서가 접미사로 가른다."""
    _import(db, "S2", [[1, "", "a", "e"], [1, "", "b", "e"], [1, "", "c", "e"]])
    assert _ids(db, "S2") == ["TC-001", "TC-001-2", "TC-001-3"]


def test_No_가_띄엄띄엄하면_그_번호를_따른다(db):
    """행을 가운데 끼워 넣어도 No 를 유지하면 같은 TC 를 따라가야 한다.
    읽은 차례로 만들면 이 성질이 깨진다."""
    _import(db, "S1", [[10, "", "s1", "e"], [20, "", "s2", "e"]])
    assert _steps(db, "S1") == {"TC-010": "s1", "TC-020": "s2"}

    _import(db, "S1", [[10, "", "s1x", "e"], [15, "", "새행", "e"], [20, "", "s2x", "e"]])

    assert _steps(db, "S1") == {"TC-010": "s1x", "TC-015": "새행", "TC-020": "s2x"}


def test_이미_저장된_행을_재임포트가_찾아낸다(db):
    """옛 코드가 만든 데이터를 흉내낸다. 이 테스트가 호환성 회귀를 막는다."""
    for i, (tid, steps) in enumerate([("TC-010", "옛1"), ("TC-020", "옛2")], start=1):
        db.add(TestCase(project_id=1, no=i, tc_id=tid, test_steps=steps,
                        expected_result="e", sheet_name="S1", created_by=1))
    db.commit()

    r = _import(db, "S1", [[10, "", "새1", "e"], [20, "", "새2", "e"]])

    assert (r["created"], r["updated"]) == (0, 2)
    assert _steps(db, "S1") == {"TC-010": "새1", "TC-020": "새2"}


# ── CSV 와 Markdown 파서도 같은 규칙을 따르는가 ──────────────────────────────
# 세 파서가 같은 코드를 베껴 쓰고 있어 한쪽만 고쳐 온 이력이 있다(SYM-25).
# 엑셀만 검증하면 나머지 둘은 조용히 갈린다.

def _csv(db, rows, sheet_name="CSV Import"):
    head = "No,TC ID,Test Steps,Expected Result"
    body = chr(10).join(",".join(str(c) for c in r) for r in rows)
    return _parse_csv((head + chr(10) + body).encode("utf-8"), 1, 1, db, sheet_name=sheet_name)


def _md(db, rows, sheet_name="MD Import"):
    lines = ["| No | TC ID | Test Steps | Expected Result |",
             "|---|---|---|---|"]
    for r in rows:
        lines.append("| " + " | ".join(str(c) for c in r) + " |")
    tables = _parse_md_tables(chr(10).join(lines).encode("utf-8"))
    assert tables, "표를 못 읽었다"
    return _parse_md_table(tables[0], 1, 1, db, sheet_name=sheet_name)


def test_CSV_도_같은_No_를_접미사로_가른다(db):
    db.add(TestCaseSheet(project_id=1, name="CSV Import", sort_order=2))
    db.commit()

    _csv(db, [[1, "", "a", "e"], [1, "", "b", "e"], [1, "", "c", "e"]])
    db.commit()

    assert _ids(db, "CSV Import") == ["TC-001", "TC-001-2", "TC-001-3"]


def test_CSV_재임포트가_각_행을_제_자리에_갱신한다(db):
    db.add(TestCaseSheet(project_id=1, name="CSV Import", sort_order=2))
    db.commit()
    _csv(db, [[1, "", "a", "e"], [1, "", "b", "e"]])
    db.commit()

    r = _csv(db, [[1, "", "ax", "e"], [1, "", "bx", "e"]])
    db.commit()

    assert (r["created"], r["updated"]) == (0, 2)
    assert _steps(db, "CSV Import") == {"TC-001": "ax", "TC-001-2": "bx"}


def test_CSV_는_No_가_없으면_폴백을_쓴다(db):
    """엑셀은 행을 버리지만 CSV 는 행 번호로 폴백한다. 예전 동작 그대로다."""
    db.add(TestCaseSheet(project_id=1, name="CSV Import", sort_order=2))
    db.commit()

    _csv(db, [["", "", "a", "e"], ["abc", "", "b", "e"]])
    db.commit()

    assert _ids(db, "CSV Import") == ["CSV-0001", "CSV-0002"]


def test_Markdown_도_같은_No_를_접미사로_가른다(db):
    db.add(TestCaseSheet(project_id=1, name="MD Import", sort_order=3))
    db.commit()

    _md(db, [[1, "", "a", "e"], [1, "", "b", "e"]])
    db.commit()

    assert _ids(db, "MD Import") == ["TC-001", "TC-001-2"]


def test_파서마다_카운터가_따로다(db):
    """seen_bases 를 공유하면 CSV 를 넣은 뒤 MD 의 첫 행이 TC-001-2 가 된다."""
    for name, order in (("CSV Import", 2), ("MD Import", 3)):
        db.add(TestCaseSheet(project_id=1, name=name, sort_order=order))
    db.commit()

    _csv(db, [[1, "", "a", "e"]])
    db.commit()
    _md(db, [[1, "", "b", "e"]])
    db.commit()

    # 시트가 다르므로 TC ID 는 프로젝트 유일성 때문에 채번이 갈라 준다.
    # 여기서 보는 것은 "MD 의 첫 행이 파서 안에서 1번째로 세어졌는가" 다.
    assert _steps(db, "CSV Import") == {"TC-001": "a"}
    assert list(_steps(db, "MD Import").values()) == ["b"]
    md_id = list(_steps(db, "MD Import"))[0]
    assert md_id.startswith("TC-001"), f"MD 의 첫 행이 다른 base 로 갔다: {md_id}"


def test_No_가_0_이어도_행을_버리지_않는다(db):
    """0 은 유효한 No 다. `not file_no` 로 판정하면 조용히 버려진다."""
    _import(db, "S1", [[0, "", "a", "e"], [1, "", "b", "e"]])
    assert _ids(db, "S1") == ["TC-000", "TC-001"]


def test_파일에_적힌_ID_와_만들어_낸_ID_가_한_이름공간이다(db):
    """TC ID 칸을 일부만 채운 파일. 두 이름공간이 나뉘면 재임포트에서 한 행이
    다른 행을 덮어 내용이 사라진다. 실측으로 확인했다."""
    _import(db, "S1", [[1, "TC-001", "a", "e"], [1, "", "b", "e"]])
    assert _steps(db, "S1") == {"TC-001": "a", "TC-001-2": "b"}

    _import(db, "S1", [[1, "TC-001", "a2", "e"], [1, "", "b2", "e"]])

    assert _steps(db, "S1") == {"TC-001": "a2", "TC-001-2": "b2"}, "한 행이 다른 행을 덮었다"


def test_명시_ID_가_파생_ID_와_부딪쳐도_갈린다(db):
    """3번 행의 명시 ID 가 2번 행이 만들어 낸 ID 와 같다."""
    rows = [[1, "", "a", "e"], [1, "", "b", "e"], [2, "TC-001-2", "c", "e"]]
    _import(db, "S1", rows)
    assert _ids(db, "S1") == ["TC-001", "TC-001-2", "TC-001-2-2"]

    _import(db, "S1", [[1, "", "a2", "e"], [1, "", "b2", "e"], [2, "TC-001-2", "c2", "e"]])

    assert _steps(db, "S1") == {"TC-001": "a2", "TC-001-2": "b2", "TC-001-2-2": "c2"}


def test_라우트_차례로도_제_자리에_갱신된다(db):
    """단위 테스트는 라우트가 하는 일의 절반만 재현한다. park -> parse -> renumber
    전체를 태워야 실제 증상(조용한 덮어쓰기)을 본다."""
    from services.tc_numbering import park_sheet_numbers, renumber_sheet

    def route(rows):
        park_sheet_numbers(1, "S1", db)
        db.flush()
        r = _parse_sheet(_sheet("S1", rows), 1, 1, db, no_offset=0, sheet_name="S1")
        db.flush()
        renumber_sheet(1, "S1", db)
        db.commit()
        return r

    route([[1, "", "a", "e"], [1, "", "b", "e"]])
    r = route([[1, "", "a2", "e"], [1, "", "b2", "e"]])

    assert (r["created"], r["updated"]) == (0, 2)
    assert _steps(db, "S1") == {"TC-001": "a2", "TC-001-2": "b2"}


def test_dedupe_in_file_직접(db):
    """allocate_tc_id 와 짝이 되는 함수라 경계값을 직접 본다."""
    from services.import_service import dedupe_in_file, tc_id_from_file_no

    used: set = set()
    assert dedupe_in_file("A-1", used) == ("A-1", False)
    assert dedupe_in_file("A-1", used) == ("A-1-2", True)
    assert dedupe_in_file("A-1", used) == ("A-1-3", True)
    # 만들어 낸 값도 점유된다. 같은 값을 명시 ID 로 넣으면 비켜 간다.
    assert dedupe_in_file("A-1-2", used) == ("A-1-2-2", True)

    used2: set = set()
    assert tc_id_from_file_no(0, used2) == ("TC-000", False)
    assert tc_id_from_file_no("007", used2) == ("TC-007", False)
    assert tc_id_from_file_no(1.9, used2) == ("TC-001", False)
    assert tc_id_from_file_no("", used2) == (None, False)
    assert tc_id_from_file_no(None, used2) == (None, False)
    assert tc_id_from_file_no("abc", used2) == (None, False)
    # 숫자가 아니면 점유를 건드리지 않는다
    assert used2 == {"TC-000", "TC-007", "TC-001"}


# ── 시트를 가로지르는 재임포트 (SYM-112) ─────────────────────────────────────
# existing_map 은 시트 단위인데 채번은 프로젝트 전체를 본다. 그래서 두 번째
# 시트의 TC-001 은 첫 시트와 부딪쳐 TC-001-2 로 저장되는데, 다음 임포트에서
# 파서는 여전히 TC-001 을 계산한다. 기존 행을 못 찾아 새로 만들고 행이 불어난다.

def _route(db, sheet_name, rows):
    """라우트와 같은 차례: park -> parse -> renumber."""
    from services.tc_numbering import park_sheet_numbers, renumber_sheet

    park_sheet_numbers(1, sheet_name, db)
    db.flush()
    r = _parse_sheet(_sheet(sheet_name, rows), 1, 1, db, no_offset=0, sheet_name=sheet_name)
    db.flush()
    renumber_sheet(1, sheet_name, db)
    db.commit()
    return r


def test_시트가_여럿이어도_재임포트가_행을_늘리지_않는다(db):
    """실측으로 2건이 4건, 6건이 됐다. 임포트할 때마다 두 배가 된다."""
    S1 = [[1, "", "a1", "e"], [2, "", "a2", "e"]]
    S2 = [[1, "", "b1", "e"], [2, "", "b2", "e"]]

    _route(db, "S1", S1)
    _route(db, "S2", S2)
    assert len(_ids(db)) == 4

    r1 = _route(db, "S1", S1)
    r2 = _route(db, "S2", S2)

    assert (r1["created"], r1["updated"]) == (0, 2)
    assert (r2["created"], r2["updated"]) == (0, 2), "두 번째 시트가 행을 새로 만들었다"
    assert len(_ids(db)) == 4, f"행이 늘었다: {_ids(db)}"


def test_세_번_넣어도_그대로다(db):
    """되짚기가 한 번만 맞고 마는 것이 아닌지 본다."""
    rows = [[1, "", "b1", "e"], [2, "", "b2", "e"]]
    _route(db, "S1", [[1, "", "a1", "e"], [2, "", "a2", "e"]])
    for _ in range(3):
        _route(db, "S2", rows)
    assert len(_ids(db, "S2")) == 2
    assert _steps(db, "S2") == {"TC-001-2": "b1", "TC-002-2": "b2"}


def test_되짚기가_파일이_적은_ID_를_가로채지_않는다(db):
    """S2 에 TC-001-2 가 있고, 파일이 그 ID 를 직접 적은 다른 행을 담고 있다.
    되짚기가 먼저 가져가면 엉뚱한 행을 덮는다."""
    _route(db, "S1", [[1, "", "a1", "e"]])
    _route(db, "S2", [[1, "", "b1", "e"]])
    assert _steps(db, "S2") == {"TC-001-2": "b1"}

    # 1번 행은 ID 를 안 적었고 2번 행이 TC-001-2 를 직접 적었다
    r = _route(db, "S2", [[1, "", "새행", "e"], [2, "TC-001-2", "b1x", "e"]])

    assert _steps(db, "S2")["TC-001-2"] == "b1x", "명시 ID 행이 제 행을 못 이었다"
    assert r["created"] == 1, "새 행이 하나 생겨야 한다"


def test_CSV_도_되짚어_찾는다(db):
    """세 파서가 같은 코드를 베껴 쓴다. 엑셀만 검증하면 나머지가 갈린다."""
    db.add(TestCaseSheet(project_id=1, name="CSV Import", sort_order=2))
    db.commit()
    # 다른 시트가 TC-001 을 먼저 차지하게 만든다
    _import(db, "S1", [[1, "", "a", "e"]])
    _csv(db, [[1, "", "b", "e"]])
    db.commit()
    assert _ids(db, "CSV Import") == ["TC-001-2"]

    r = _csv(db, [[1, "", "bx", "e"]])
    db.commit()

    assert (r["created"], r["updated"]) == (0, 1), "되짚지 못해 새로 만들었다"
    assert _steps(db, "CSV Import") == {"TC-001-2": "bx"}


def test_Markdown_도_되짚어_찾는다(db):
    db.add(TestCaseSheet(project_id=1, name="MD Import", sort_order=3))
    db.commit()
    _import(db, "S1", [[1, "", "a", "e"]])
    _md(db, [[1, "", "b", "e"]])
    db.commit()
    assert _ids(db, "MD Import") == ["TC-001-2"]

    r = _md(db, [[1, "", "bx", "e"]])
    db.commit()

    assert (r["created"], r["updated"]) == (0, 1)
    assert _steps(db, "MD Import") == {"TC-001-2": "bx"}


def test_빈_시트_첫_임포트는_되짚기의_영향을_받지_않는다(db):
    """되짚기는 재임포트에서만 동작해야 한다. 빈 시트에서는 existing_map 이
    비어 있어 첫 후보에서 바로 끝난다."""
    r = _import(db, "S1", [[1, "", "a", "e"], [2, "", "b", "e"]])
    assert (r["created"], r["updated"], r["renamed"]) == (2, 0, 0)
    assert _ids(db, "S1") == ["TC-001", "TC-002"]


def test_되짚기_후보가_연달아_있어도_끝난다(db):
    """base-2, base-3 이 모두 파일이 적은 ID 면 더 볼 것이 없다. 무한 루프가
    아니라 새로 만드는 쪽으로 끝나야 한다."""
    _import(db, "S1", [[1, "TC-001-2", "x", "e"], [2, "TC-001-3", "y", "e"]])
    assert _ids(db, "S1") == ["TC-001-2", "TC-001-3"]

    # 같은 파일에 No 1 짜리 행을 더한다. TC-001 은 없고 -2, -3 은 파일이 적었다
    r = _import(db, "S1", [[1, "TC-001-2", "x", "e"], [2, "TC-001-3", "y", "e"], [1, "", "새행", "e"]])

    assert r["created"] == 1, "되짚기가 남의 행을 가져갔다"
    assert _steps(db, "S1")["TC-001-2"] == "x"
    assert _steps(db, "S1")["TC-001-3"] == "y"


def test_세_번째_시트도_되짚는다(db):
    """S3 의 파킹 ID 는 TC-001-3 인데 TC-001-2 는 S2 소유라 이 시트 맵에 없다.
    접미사를 2, 3 으로 세어 올라가면 첫 구멍에서 끊긴다."""
    db.add(TestCaseSheet(project_id=1, name="S3", sort_order=4))
    db.commit()
    data = {n: [[1, "", f"{n}-a", "e"]] for n in ("S1", "S2", "S3")}
    for n in ("S1", "S2", "S3"):
        _route(db, n, data[n])
    assert len(_ids(db)) == 3

    for n in ("S1", "S2", "S3"):
        r = _route(db, n, data[n])
        assert (r["created"], r["updated"]) == (0, 1), f"{n} 가 행을 새로 만들었다"
    assert len(_ids(db)) == 3, f"행이 늘었다: {_ids(db)}"


def test_사람이_붙인_ID_를_덮지_않는다(db):
    """되짚기가 만든 회귀를 막는다. base 가 프로젝트 어디에도 없으면 그 base-2 는
    채번이 만든 것이 아니라 사람이 손으로 붙인 것이다.

    ★파일이 그 ID 를 적지 않았으므로 explicit 가드로는 못 막는다. HEAD 는 새 행을
      만들어 둘 다 살렸다. 덮어쓰면 회귀다.
    """
    db.add(TestCase(project_id=1, no=9, tc_id="TC-005-2", test_steps="사람이 붙인 행",
                    expected_result="e", sheet_name="S1", created_by=1))
    db.commit()

    r = _route(db, "S1", [[5, "", "전혀 다른 새 행", "e"]])

    assert r["created"] == 1, "기존 행을 덮었다"
    assert _steps(db, "S1") == {"TC-005": "전혀 다른 새 행", "TC-005-2": "사람이 붙인 행"}


def test_되짚기_단위_동작(db):
    """라우트를 태우지 않고 경계값을 직접 본다."""
    from services.import_service import find_parked_by_base
    from services.tc_id_service import allocate_tc_id

    taken = {"TC-001"}
    # base 가 taken 에 있어야 되짚는다
    assert find_parked_by_base("TC-001", {"TC-001-2": 1}, set(), taken) == "TC-001-2"
    assert find_parked_by_base("TC-001", {"TC-001-2": 1}, set(), set()) is None
    # 비연속 후보도 찾는다(세 번째 시트)
    assert find_parked_by_base("TC-001", {"TC-001-3": 1}, set(), taken) == "TC-001-3"
    # 접미사가 작은 것을 고른다
    assert find_parked_by_base("TC-001", {"TC-001-5": 1, "TC-001-2": 1}, set(), taken) == "TC-001-2"
    # 파일이 적은 ID 는 건너뛴다
    assert find_parked_by_base("TC-001", {"TC-001-2": 1}, {"TC-001-2"}, taken) is None
    # 빈 맵
    assert find_parked_by_base("TC-001", {}, set(), taken) is None
    # 다른 base 의 것은 가져가지 않는다
    assert find_parked_by_base("TC-001", {"TC-002-2": 1}, set(), taken) is None

    # 길이 상한을 넘으면 채번이 잘라 저장한다. 되짚기도 같은 규칙을 알아야 한다.
    long_base = "L" * 49
    stored = allocate_tc_id(long_base, {long_base})
    assert find_parked_by_base(long_base, {stored: 1}, set(), {long_base}) == stored


def test_서식만_있는_빈_구간이_임포트를_느리게_하지_않는다(db):
    """explicit_ids 스캔이 ws.max_row 까지 훑으면서 셀마다 병합 범위를 전부
    보면, 서식 때문에 max_row 가 부푼 워크북에서 임포트가 멈춘 것처럼 느려진다.
    실측으로 0.16초가 109초가 됐다."""
    import time
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "S1"
    ws.append(["No", "TC ID", "Test Steps", "Expected Result"])
    for i in range(1, 201):
        ws.append([i, "", f"s{i}", "e"])
    ws.cell(row=20000, column=8).value = " "          # max_row 를 부풀린다
    for m in range(300):                               # 병합을 많이 둔다
        r = 2 + (m % 200)
        ws.merge_cells(start_row=r, start_column=6, end_row=r, end_column=7)

    t = time.perf_counter()
    r = _parse_sheet(ws, 1, 1, db, no_offset=0, sheet_name="S1")
    elapsed = time.perf_counter() - t

    assert r["created"] == 200
    assert elapsed < 3.0, f"{elapsed:.1f}초 걸렸다. 빈 구간이나 병합 훑기가 되살아났다"
