"""임포트가 폴더에 TC 를 넣지 않는다

API 로 만들 때는 `_validate_sheet_name` 이 "폴더에는 TC 를 직접 추가할 수 없습니다"
로 막는데, 임포트 세 경로는 그 검증을 거치지 않고 이름만 보고 진행했다.

폴더에 들어간 TC 는 `leaf_sheet_order.walk` 가 폴더를 걷어 내면서 정렬에서 빠지고,
`create_testrun` 이 그 시트를 런 범위로 받지 않는다. 즉 수행에 담을 수 없는 TC 가
생긴다.

실행: cd backend && TEST_PORT=8099 TEST_BASE_URL=http://127.0.0.1:8099 python -m pytest test_import_folder_sheet.py -v
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
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__import_folder__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _make_xlsx(sheet_name: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name
    ws.append(["TC ID", "Category", "Test Steps", "Expected Result", "Priority"])
    ws.append(["TC-IMP-001", "기본", "1. 실행", "성공", "보통"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_폴더_이름의_시트로는_임포트할_수_없다(token, project):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                      json={"name": "묶음", "parent_id": None, "is_folder": True})
    assert r.status_code in (200, 201), r.text

    files = {"file": ("tc.xlsx", _make_xlsx("묶음"),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    imp = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                        headers=h, files=files)
    assert imp.status_code == 400, f"폴더에 TC 가 들어갔다: {imp.status_code} {imp.text}"

    tcs = requests.get(f"{BASE}/api/projects/{project}/testcases", headers=h).json()
    assert all(tc["sheet_name"] != "묶음" for tc in tcs), "폴더에 TC 가 남았다"


def test_일반_시트로는_임포트할_수_있다(token, project):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                      json={"name": "결제", "parent_id": None, "is_folder": False})
    assert r.status_code in (200, 201), r.text

    files = {"file": ("tc.xlsx", _make_xlsx("결제"),
                      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    imp = requests.post(f"{BASE}/api/projects/{project}/testcases/import",
                        headers=h, files=files)
    assert imp.status_code in (200, 201), imp.text

    tcs = requests.get(f"{BASE}/api/projects/{project}/testcases", headers=h).json()
    assert any(tc["sheet_name"] == "결제" for tc in tcs), "임포트가 아무것도 넣지 않았다"
