"""TC 목록 Markdown 내보내기 (SYM-211)

내보낸 파일은 Markdown 가져오기가 읽는 표 형식과 같아야 한다. 그래서 검증 기준을
"문자열이 이렇게 생겼다" 가 아니라 "가져오기 파서로 되읽으면 원문과 같다" 로 둔다.
문자열을 박아 두면 구현을 베낀 테스트가 되고, 파서와 어긋나도 통과한다.

실행: cd backend && python -m pytest tests_unit/test_export_markdown.py -q
"""
import asyncio
import os
import sys
from types import SimpleNamespace

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from services.export_service import build_testcases_markdown, export_testcases_markdown
from services.import_service import _parse_md_tables, map_header

NL = chr(10)
FIELDS = [
    "no", "tc_id", "type", "category", "depth1", "depth2", "priority",
    "test_type", "precondition", "test_steps", "expected_result", "remarks",
]


def _tc(**kw):
    base = {f: None for f in FIELDS}
    base["sheet_name"] = None
    base.update(kw)
    return SimpleNamespace(**base)


PROJECT = SimpleNamespace(name="결제 앱")


def _rows_by_field(table):
    """가져오기와 같은 방식으로 머리글을 필드에 대응시켜 행을 dict 로 돌려준다."""
    col_map = {}
    for i, h in enumerate(table["headers"]):
        f = map_header(h, combined=True)
        if f and f != "_skip":
            col_map[i] = f
    out = []
    for cells in table["rows"]:
        out.append({f: (cells[i] if i < len(cells) else "") for i, f in col_map.items()})
    return out


def test_every_field_survives_import_parser():
    tc = _tc(
        no=1, tc_id="PAY-001", type="Functional", category="결제", depth1="카드", depth2="해외",
        priority="High", test_type="Android", precondition="로그인한 상태",
        test_steps=NL.join(["1. 앱을 연다", "2. 결제 | 카드 선택", "   - 해외 카드"]),
        expected_result="승인 a" + chr(92) + "|b 표시", remarks="비고",
        sheet_name="결제",
    )
    tables = _parse_md_tables(build_testcases_markdown(PROJECT, [tc], split_sheets=False).encode("utf-8"))
    assert len(tables) == 1
    row = _rows_by_field(tables[0])[0]
    for f in FIELDS:
        expected = "" if getattr(tc, f) is None else str(getattr(tc, f))
        assert row.get(f) == expected, f


def test_crlf_and_none_values():
    tc = _tc(no=1, tc_id="TC-1", test_steps="1. 가" + chr(13) + NL + "2. 나", sheet_name="A")
    tables = _parse_md_tables(build_testcases_markdown(PROJECT, [tc], split_sheets=False).encode("utf-8"))
    row = _rows_by_field(tables[0])[0]
    assert row["test_steps"] == "1. 가" + NL + "2. 나"
    assert row["remarks"] == ""
    assert row["precondition"] == ""


def test_split_sheets_one_table_per_sheet_in_given_order():
    tcs = [
        _tc(no=1, tc_id="B-1", sheet_name="나시트"),
        _tc(no=2, tc_id="B-2", sheet_name="나시트"),
        _tc(no=1, tc_id="A-1", sheet_name="가시트"),
        _tc(no=1, tc_id="N-1", sheet_name=None),
    ]
    tables = _parse_md_tables(build_testcases_markdown(PROJECT, tcs, split_sheets=True).encode("utf-8"))
    assert [t["name"] for t in tables] == ["나시트", "가시트", "기본"]
    assert [[r["tc_id"] for r in _rows_by_field(t)] for t in tables] == [["B-1", "B-2"], ["A-1"], ["N-1"]]


def test_merged_mode_is_single_table():
    tcs = [_tc(no=1, tc_id="B-1", sheet_name="나"), _tc(no=1, tc_id="A-1", sheet_name="가")]
    tables = _parse_md_tables(build_testcases_markdown(PROJECT, tcs, split_sheets=False).encode("utf-8"))
    assert [t["name"] for t in tables] == ["Test Cases"]
    assert [r["tc_id"] for r in _rows_by_field(tables[0])] == ["B-1", "A-1"]


def test_expand_refs_option():
    src = _tc(no=1, tc_id="TC-001", precondition=NL.join(["1. 로그인", "2. 장바구니에 상품"]), sheet_name="A")
    ref = _tc(no=2, tc_id="TC-002", precondition="TC-001 의 사전조건 참조", sheet_name="A")

    kept = _parse_md_tables(build_testcases_markdown(PROJECT, [src, ref], False, expand_refs=False).encode("utf-8"))
    assert _rows_by_field(kept[0])[1]["precondition"] == "TC-001 의 사전조건 참조"

    expanded = _parse_md_tables(build_testcases_markdown(PROJECT, [src, ref], False, expand_refs=True).encode("utf-8"))
    assert _rows_by_field(expanded[0])[1]["precondition"] == NL.join(["1. 로그인", "2. 장바구니에 상품"])


@pytest.mark.parametrize("split", [False, True])
def test_empty_project_does_not_crash(split):
    text = build_testcases_markdown(PROJECT, [], split_sheets=split)
    assert "TC ID" in text
    assert _parse_md_tables(text.encode("utf-8")) == []


def test_import_turns_br_back_into_newlines():
    md = NL.join([
        "## 시트",
        "| TC ID | Steps |",
        "|---|---|",
        "| T-1 | 1. 가<br>2. 나<br/>3. 다<BR />4. 라 |",
    ])
    table = _parse_md_tables(md.encode("utf-8"))[0]
    assert table["rows"][0][1] == NL.join(["1. 가", "2. 나", "3. 다", "4. 라"])


def test_response_headers():
    resp = export_testcases_markdown(PROJECT, [_tc(no=1, tc_id="T-1", sheet_name="A")], split_sheets=False)
    assert resp.media_type.startswith("text/markdown")
    assert "charset=utf-8" in resp.media_type
    disp = resp.headers["content-disposition"]
    assert disp.endswith(".md")
    assert "UTF-8''" in disp

    async def collect():
        return b"".join([c if isinstance(c, bytes) else c.encode() async for c in resp.body_iterator])

    body = asyncio.run(collect()).decode("utf-8")
    assert "T-1" in body


# ── 라우트: 형식 분기와 시트 차례 ─────────────────────────────────────────────

from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseSheet, User
from routes.testcases import export_testcases


@pytest.fixture
def db(pg_engine):
    s = sessionmaker(bind=pg_engine)()
    yield s
    s.close()


@pytest.fixture
def seeded(db):
    """시트 생성 순서(다, 가)를 이름 순서와 어긋나게 둔다. 같으면 정렬을 빼도 통과한다."""
    user = User(username="admin", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    for order, name in enumerate(["다시트", "가시트"]):
        db.add(TestCaseSheet(project_id=project.id, name=name, sort_order=order, is_folder=False))
    for sheet in ["가시트", "다시트"]:
        for i in (2, 1):
            db.add(TestCase(project_id=project.id, no=i, tc_id=f"{sheet}-{i}", sheet_name=sheet,
                            test_steps="1. 실행", created_by=user.id))
    db.commit()
    return project, user


def _call(db, seeded, **kw):
    project, user = seeded
    params = {"split_sheets": False, "expand_refs": False, "file_format": "xlsx"}
    params.update(kw)
    return export_testcases(project_id=project.id, db=db, current_user=user, **params)


def _body(resp):
    async def collect():
        return b"".join([c if isinstance(c, bytes) else c.encode() async for c in resp.body_iterator])
    return asyncio.run(collect())


def test_route_md_split_follows_sheet_order(db, seeded):
    resp = _call(db, seeded, split_sheets=True, file_format="md")
    assert resp.media_type.startswith("text/markdown")
    tables = _parse_md_tables(_body(resp))
    assert [t["name"] for t in tables] == ["다시트", "가시트"]
    assert [[r["tc_id"] for r in _rows_by_field(t)] for t in tables] == [
        ["다시트-1", "다시트-2"], ["가시트-1", "가시트-2"],
    ]


def test_route_default_is_still_xlsx(db, seeded):
    resp = _call(db, seeded)
    assert resp.media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert _body(resp)[:2] == b"PK"


@pytest.mark.parametrize("raw", [
    "화면에 <br> 태그가 글자로 보인다",
    "a<BR/>b",
    "&lt;br&gt; 를 입력",
    "&amp;lt; 그대로",
    "<script>alert(1)</script>",
    "A && B > C",
    "&&lt;",
    "끝 역슬래시" + chr(92) + NL + "다음 줄",
    chr(92) + "&amp;",
])
def test_html_like_text_survives(raw):
    """원문의 <br> 글자와 엔티티 글자가 줄바꿈이나 다른 글자로 바뀌면 안 된다."""
    tc = _tc(no=1, tc_id="T-1", expected_result=raw, sheet_name="A")
    tables = _parse_md_tables(build_testcases_markdown(PROJECT, [tc], split_sheets=False).encode("utf-8"))
    assert _rows_by_field(tables[0])[0]["expected_result"] == raw


def test_sheet_name_with_newline_stays_one_heading():
    tcs = [_tc(no=1, tc_id="T-1", sheet_name="가" + NL + "## 나")]
    tables = _parse_md_tables(build_testcases_markdown(PROJECT, tcs, split_sheets=True).encode("utf-8"))
    assert [t["name"] for t in tables] == ["가 ## 나"]


def test_project_name_cannot_inject_a_table():
    """프로젝트 이름은 줄바꿈을 막지 않는다. 그대로 쓰면 이름 속 표가 TC 로 읽힌다."""
    name = NL.join(["P", "| TC ID | Steps |", "|---|---|", "| INJ-1 | x |"])
    text = build_testcases_markdown(SimpleNamespace(name=name), [], split_sheets=False)
    assert _parse_md_tables(text.encode("utf-8")) == []


def test_route_md_merged_follows_sheet_order(db, seeded):
    """SYM-44 가 실제로 터진 곳은 통합 모드다(시트가 한 줄씩 번갈아 나왔다)."""
    tables = _parse_md_tables(_body(_call(db, seeded, file_format="md")))
    assert [r["tc_id"] for r in _rows_by_field(tables[0])] == ["다시트-1", "다시트-2", "가시트-1", "가시트-2"]


# ── 실제 가져오기 경로로 되올리기 ─────────────────────────────────────────────

import io

from fastapi import UploadFile

from routes.testcases import import_testcases

TRICKY = {
    "test_steps": NL.join(["1. 결제 | 카드", "2. <br> 글자 확인", "   - 하위"]),
    "expected_result": "a" + chr(92) + "|b & <b>",
    "precondition": "로그인",
    "priority": "높음",
}


def _md_of(db, project, user, split=True):
    resp = export_testcases(project_id=project.id, split_sheets=split, expand_refs=False,
                            file_format="md", db=db, current_user=user)
    return _body(resp)


def _import(db, project, user, data):
    return import_testcases(project_id=project.id, file=UploadFile(file=io.BytesIO(data), filename="t.md"),
                            sheet_names=None, upload_id=None, db=db, current_user=user)


def _snapshot(db, project_id):
    rows = (db.query(TestCase)
            .filter(TestCase.project_id == project_id, TestCase.deleted_at.is_(None))
            .order_by(TestCase.sheet_name, TestCase.no).all())
    return [(r.sheet_name, r.no, r.tc_id, r.test_steps, r.expected_result, r.precondition, r.priority)
            for r in rows]


def test_import_of_export_recreates_same_tcs(db, seeded):
    project, user = seeded
    for tc in db.query(TestCase).filter(TestCase.project_id == project.id):
        for k, v in TRICKY.items():
            setattr(tc, k, v)
    db.commit()
    before = _snapshot(db, project.id)

    other = Project(name="Q", created_by=user.id)
    db.add(other)
    db.commit()
    res = _import(db, other, user, _md_of(db, project, user))
    assert res["created"] == 4 and res["updated"] == 0
    assert _snapshot(db, other.id) == before


def test_reimport_into_same_project_updates_not_duplicates(db, seeded):
    project, user = seeded
    before = _snapshot(db, project.id)
    res = _import(db, project, user, _md_of(db, project, user))
    assert (res["created"], res["updated"], res["renamed"]) == (0, 4, 0)
    assert _snapshot(db, project.id) == before


# ── HTTP: 쿼리 이름 format, 기본값, 잘못된 값 ───────────────────────────────────

import requests

from auth_helpers import bearer, login, make_user
from models import UserRole


def test_http_format_param(auth_env):
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    h = bearer(login(auth_env.base, "boss"))
    r = requests.post(auth_env.base + "/api/projects", headers=h, json={"name": "MDX"})
    assert r.status_code == 201, r.text
    url = f"{auth_env.base}/api/projects/{r.json()['id']}/testcases/export"

    default = requests.get(url, headers=h)
    assert default.status_code == 200
    assert default.headers["content-type"].startswith("application/vnd.openxmlformats")

    md = requests.get(url, headers=h, params={"format": "md"})
    assert md.status_code == 200
    assert md.headers["content-type"].startswith("text/markdown")
    assert md.content.decode("utf-8").startswith("# MDX")

    assert requests.get(url, headers=h, params={"format": "pdf"}).status_code == 422
