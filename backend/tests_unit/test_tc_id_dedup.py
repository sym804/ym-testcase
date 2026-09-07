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
from services.import_service import _parse_sheet
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
