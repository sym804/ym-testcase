"""가져오기 머리글은 대소문자와 앞뒤 · 겹친 공백을 가리지 않는다

"Expected result", "Test steps" 처럼 대소문자만 다른 머리글이 매핑되지 않아 그 칸이 통째로
빠졌다. 정확히 같은 머리글의 매핑(Platform -> test_type 등)은 그대로다.

실행: cd backend && python -m pytest tests_unit/test_import_header_case.py -q
"""
import io

import pytest
import requests
from openpyxl import Workbook

from auth_helpers import bearer, login, make_user
from models import TestCase, UserRole


@pytest.fixture
def admin(auth_env):
    make_user(auth_env.Session, username="root", role=UserRole.admin)
    h = bearer(login(auth_env.base, "root"))
    r = requests.post(auth_env.base + "/api/projects", json={"name": "P"}, headers=h)
    assert r.status_code in (200, 201), r.text
    return auth_env, h, r.json()["id"]


def _tcs(env, pid):
    s = env.Session()
    try:
        return {t.tc_id: t for t in s.query(TestCase).filter(TestCase.project_id == pid).all()}
    finally:
        s.close()


def _import(env, h, pid, name, body):
    r = requests.post(f"{env.base}/api/projects/{pid}/testcases/import",
                      files={"file": (name, body)}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "S1"
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_map_header_는_대소문자와_공백을_가리지_않는다():
    from services.import_service import map_header

    assert map_header("Expected result") == "expected_result"
    assert map_header("  test STEPS ") == "test_steps"
    assert map_header("Precondition  /  test data") == "precondition"
    assert map_header("tc id") == "tc_id"
    # 정확히 같은 머리글은 예전 매핑 그대로
    assert map_header("Platform") == "test_type"
    assert map_header("Actual Result") == "remarks"
    assert map_header("모르는 칸") is None
    # CSV · 마크다운은 Jira 머리글까지 본다
    assert map_header("issue KEY", combined=True) == "tc_id"
    assert map_header("issue KEY") is None


def test_엑셀_머리글_대소문자가_달라도_칸이_들어간다(admin):
    env, h, pid = admin
    _import(env, h, pid, "t.xlsx", _xlsx([
        ["no", "tc id", "Test steps", "Expected result", "PRIORITY", " Category "],
        [1, "TC-1", "열기", "열린다", "High", "로그인"],
    ]))
    tc = _tcs(env, pid)["TC-1"]
    assert (tc.test_steps, tc.expected_result, tc.priority, tc.category) == ("열기", "열린다", "High", "로그인")


def test_CSV_머리글_대소문자가_달라도_칸이_들어간다(admin):
    env, h, pid = admin
    _import(env, h, pid, "t.csv", "TC id,Test Steps,expected RESULT\nC-1,a,b\n".encode("utf-8"))
    tc = _tcs(env, pid)["C-1"]
    assert (tc.test_steps, tc.expected_result) == ("a", "b")


def test_마크다운_머리글_대소문자가_달라도_칸이_들어간다(admin):
    env, h, pid = admin
    _import(env, h, pid, "t.md", "# 시트\n| Tc Id | Test steps | Expected result |\n|---|---|---|\n| M-1 | a | b |\n"
            .encode("utf-8"))
    tc = _tcs(env, pid)["M-1"]
    assert (tc.test_steps, tc.expected_result) == ("a", "b")


def test_CSV_열이_머리글보다_적은_행은_빈_칸으로_읽는다(admin):
    """DictReader 는 모자란 칸을 None 으로 채운다. 예전에는 .strip() 에서 500 이 났다."""
    env, h, pid = admin
    _import(env, h, pid, "t.csv", "TC ID,Priority,Test Steps\nTC-001\nTC-002,High\n".encode("utf-8"))
    tcs = _tcs(env, pid)
    assert tcs["TC-001"].priority is None and tcs["TC-001"].test_steps is None
    assert tcs["TC-002"].priority == "High"
