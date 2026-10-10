"""입력 길이 초과가 500 으로 떨어지지 않는다

PostgreSQL 은 VARCHAR(n) 을 넘는 값을 넣으면 DataError(StringDataRightTruncation)를 낸다.
SQLite 는 길이를 보지 않아 드러나지 않았다. 세 겹으로 막는다.

- 스키마가 컬럼 길이와 같은 max_length 로 먼저 거절한다(422).
- 가져오기(엑셀 · CSV · 마크다운)는 넘는 칸을 잘라 넣지 않고, 행과 칸을 모아 400 으로 거절한다.
- 그래도 새는 경로는 전역 핸들러가 400 과 안내 문구로 바꾼다.

실행: cd backend && python -m pytest tests_unit/test_length_limits.py -q
"""
import asyncio
import io
import json
import os
import sys

import pytest
import requests
from annotated_types import MaxLen
from openpyxl import Workbook
from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.exc import DataError

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import models
import schemas
from routes.api_keys import ApiKeyCreate
from routes.sheets import _SheetCreate, _SheetRename
from auth_helpers import bearer, login, make_user
from models import Project, TestCase, TestCaseSheet, User, UserRole


# ── 전역 핸들러 ──────────────────────────────────────────────────────────────

def _overlong_error(s):
    u = User(username="u", password_hash="x", display_name="u")
    s.add(u)
    s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p)
    s.flush()
    s.add(TestCaseSheet(project_id=p.id, name="x" * 101, sort_order=0))
    with pytest.raises(DataError) as e:
        s.flush()
    s.rollback()
    return e.value


def test_길이_초과_DataError_는_400_과_안내_문구(pg_session):
    from starlette.requests import Request
    from main import app, data_error_handler

    exc = _overlong_error(pg_session)
    assert DataError in app.exception_handlers, "전역 핸들러로 등록돼야 라우트 밖에서도 잡힌다"
    req = Request({"type": "http", "method": "POST", "path": "/api/x", "headers": []})
    resp = asyncio.run(data_error_handler(req, exc))
    assert resp.status_code == 400
    assert "길이" in json.loads(resp.body)["detail"]


# ── 스키마 길이 = 컬럼 길이 ─────────────────────────────────────────────────

#: (스키마, 모델, {스키마 필드: 모델 컬럼}). 매핑에 없는 필드는 이름이 같은 컬럼을 본다.
SCHEMA_MODEL = [
    (schemas.TestCaseCreate, models.TestCase, {}),
    (schemas.TestCaseUpdate, models.TestCase, {}),
    (schemas.TestCaseBulkItem, models.TestCase, {}),
    (schemas.TestRunCreate, models.TestRun, {}),
    (schemas.TestRunUpdate, models.TestRun, {}),
    (schemas.TestResultCreate, models.TestResult, {}),
    (schemas.TestResultUpdate, models.TestResult, {}),
    (schemas.TestPlanCreate, models.TestPlan, {}),
    (schemas.TestPlanUpdate, models.TestPlan, {}),
    (schemas.ProjectCreate, models.Project, {}),
    (schemas.ProjectUpdate, models.Project, {}),
    (schemas.CustomFieldDefCreate, models.CustomFieldDef, {}),
    (schemas.CustomFieldDefUpdate, models.CustomFieldDef, {}),
    (schemas.SavedFilterCreate, models.SavedFilter, {}),
    (schemas.SavedFilterUpdate, models.SavedFilter, {}),
    (schemas.RunIssueCreate, models.RunIssue, {}),
    (schemas.RunIssueUpdate, models.RunIssue, {}),
    (schemas.UserCreate, models.User, {}),
    (schemas.AccountRequestCreate, models.AccountRequest, {}),
    (_SheetCreate, models.TestCaseSheet, {}),
    (_SheetRename, models.TestCaseSheet, {"new_name": "name"}),
    (ApiKeyCreate, models.ApiKey, {}),
]


def _max_len(field):
    for m in field.metadata:
        if isinstance(m, MaxLen):
            return m.max_length
    return None


@pytest.mark.parametrize("schema,model,alias", SCHEMA_MODEL, ids=lambda x: getattr(x, "__name__", ""))
def test_스키마_max_length_가_컬럼_길이와_같다(schema, model, alias):
    cols = model.__table__.columns
    checked = 0
    wrong = []
    for name, field in schema.model_fields.items():
        col = cols.get(alias.get(name, name))
        # Enum 칸은 값 목록으로 따로 검증한다(라우트가 TestResultValue 등으로 거절한다).
        if (col is None or not isinstance(col.type, String) or isinstance(col.type, SAEnum)
                or col.type.length is None):
            continue
        checked += 1
        if _max_len(field) != col.type.length:
            wrong.append(f"{name}: 스키마 {_max_len(field)} != 컬럼 {col.type.length}")
    assert checked, "비교한 필드가 없다. 매핑이 틀렸다"
    assert not wrong, wrong


def test_R1_에_Not_Applicable_은_스키마가_거절한다():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        schemas.TestCaseCreate(tc_id="A-1", r1="Not Applicable")
    with pytest.raises(ValidationError):
        schemas.TestCaseBulkItem(id=1, r1="Not Applicable")


# ── HTTP: 생성 · 가져오기 ───────────────────────────────────────────────────

@pytest.fixture
def admin(auth_env):
    make_user(auth_env.Session, username="root", role=UserRole.admin)
    h = bearer(login(auth_env.base, "root"))
    r = requests.post(auth_env.base + "/api/projects", json={"name": "P"}, headers=h)
    assert r.status_code in (200, 201), r.text
    return auth_env, h, r.json()["id"]


def _tc_count(env, pid):
    s = env.Session()
    try:
        return s.query(TestCase).filter(TestCase.project_id == pid).count()
    finally:
        s.close()


def test_TC_생성의_긴_R1_은_500_이_아니다(admin):
    env, h, pid = admin
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases",
                      json={"tc_id": "A-1", "r1": "Not Applicable"}, headers=h)
    assert r.status_code == 422, r.text


def test_시트_생성의_긴_이름은_500_이_아니다(admin):
    env, h, pid = admin
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/sheets", json={"name": "가" * 101}, headers=h)
    assert r.status_code == 422, r.text


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "S1"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_엑셀_가져오기의_긴_R1_은_행과_칸을_알려_400(admin):
    env, h, pid = admin
    body = _xlsx([
        ["No", "TC ID", "Category", "Test Steps", "Expected Result", "R1"],
        [1, "TC-1", "c", "s", "e", "PASS"],
        [2, "TC-2", "c", "s", "e", "Not Applicable"],
    ])
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.xlsx", body)}, headers=h)
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "R1" in detail and "3행" in detail and "S1" in detail, detail
    # 잘라 넣지 않고 통째로 거절한다. 멀쩡한 행도 남지 않는다.
    assert _tc_count(env, pid) == 0


def test_CSV_가져오기의_긴_우선순위는_400(admin):
    env, h, pid = admin
    body = ("TC ID,Priority,Test Steps\nC-1,High,s\nC-2," + "P" * 21 + ",s\n").encode("utf-8")
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.csv", body)}, headers=h)
    assert r.status_code == 400, r.text
    assert "Priority" in r.json()["detail"]
    assert _tc_count(env, pid) == 0


def test_CSV_가져오기의_50자를_넘는_TC_ID_는_행을_알려_400(admin):
    """잘라 넣으면 다시 가져올 때 같은 TC 를 못 찾아 행이 늘어난다. 잘라 넣지 않고 알린다."""
    env, h, pid = admin
    body = ("TC ID,Test Steps\nC-1,s\n" + "T" * 51 + ",s\n").encode("utf-8")
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.csv", body)}, headers=h)
    assert r.status_code == 400, r.text
    assert "TC ID(51/50자)" in r.json()["detail"]
    assert _tc_count(env, pid) == 0


def test_CSV_안에서_50자_TC_ID_가_두_번_나와도_가져온다(admin):
    """파일 안 중복에 붙이는 `-2` 도 채번처럼 50자 안으로 맞춘다. 안 맞추면 52자가 돼 전체가 거절됐다."""
    env, h, pid = admin
    tc_id = "T" * 50
    body = ("TC ID,Test Steps\n" + tc_id + ",a\n" + tc_id + ",b\n").encode("utf-8")
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.csv", body)}, headers=h)
    assert r.status_code in (200, 201), r.text
    assert _tc_count(env, pid) == 2


def test_마크다운_가져오기의_긴_R1_은_400(admin):
    env, h, pid = admin
    body = "# 시트\n| TC ID | R1 |\n|---|---|\n| M-1 | Not Applicable |\n".encode("utf-8")
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.md", body)}, headers=h)
    assert r.status_code == 400, r.text
    assert "R1" in r.json()["detail"]
    assert _tc_count(env, pid) == 0


def test_마크다운_제목이_시트_이름_길이를_넘으면_400(admin):
    env, h, pid = admin
    body = ("# " + "가" * 101 + "\n| TC ID | R1 |\n|---|---|\n| M-1 | PASS |\n").encode("utf-8")
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.md", body)}, headers=h)
    assert r.status_code == 400, r.text
    assert "시트 이름" in r.json()["detail"]


def test_길이_안의_가져오기는_그대로_된다(admin):
    env, h, pid = admin
    body = _xlsx([
        ["No", "TC ID", "Priority", "R1"],
        [1, "TC-1", "High", "N/A"],
    ])
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": ("t.xlsx", body)}, headers=h)
    assert r.status_code == 201, r.text
    assert _tc_count(env, pid) == 1
