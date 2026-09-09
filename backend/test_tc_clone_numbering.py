"""TC 복제가 주는 번호는 시트 안 순번이다.

`no` 는 시트 안에서 1 부터 이어지는 순번이다. 신규 행 추가(프론트가 그 시트의
max+1 을 보낸다)와 엑셀 임포트(`no_offset=0`)는 그 규약을 지키는데, 복제만
프로젝트 전체 max(no)+1 을 줬다. 그래서 시트 안 번호에 구멍이 생겼고, 그 시트로
만든 테스트 수행의 No 가 1 부터 시작하지 않았다.

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_tc_clone_numbering.py -v
"""
import os

import pytest
import requests

BASE = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8008")
ADMIN_PW = os.getenv("TEST_ADMIN_PASSWORD", "test1234")

if BASE.endswith(":8008") and os.getenv("ALLOW_DEV_DB") != "1":
    pytest.skip(
        "개발 서버(8008)의 실 DB 오염 방지를 위해 건너뜀. "
        "격리 실행: TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 pytest test_tc_clone_numbering.py",
        allow_module_level=True,
    )


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": ADMIN_PW})
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def _add_tc(token, pid, no, tc_id, sheet):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json={
        "no": no, "tc_id": tc_id, "category": sheet, "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": sheet, "priority": "High",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def project(token):
    """로그인 시트에 3건(no 1~3), 결제 시트에 2건(no 1~2).

    시트마다 번호가 1 부터 다시 시작한다. 프로젝트 전체 max(no) 는 3 이라
    시트 기준(결제의 max 는 2)과 값이 갈린다.
    """
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__clone_no__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]

    ids = {}
    for sheet, count in (("로그인", 3), ("결제", 2)):
        rs = requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                           json={"name": sheet, "parent_id": None, "is_folder": False})
        assert rs.status_code in (200, 201), rs.text
        for i in range(1, count + 1):
            ids[(sheet, i)] = _add_tc(token, pid, i, f"TC-{sheet}-{i:03d}", sheet)

    yield pid, ids
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _nos_of(token, pid, sheet):
    r = requests.get(f"{BASE}/api/projects/{pid}/testcases",
                     headers=auth(token), params={"sheet_name": sheet})
    assert r.status_code == 200, r.text
    return sorted(tc["no"] for tc in r.json())


def test_clone_uses_sheet_max(token, project):
    """한 건 복제는 그 시트의 max+1 을 받는다."""
    pid, ids = project
    r = requests.post(
        f"{BASE}/api/projects/{pid}/testcases/{ids[('결제', 2)]}/clone", headers=auth(token))
    assert r.status_code == 201, r.text
    assert r.json()["no"] == 3, "결제 시트의 max(no)=2 이므로 3 이어야 한다"
    assert _nos_of(token, pid, "결제") == [1, 2, 3]


def test_bulk_clone_numbers_within_each_sheet(token, project):
    """여러 시트를 한 번에 복제해도 번호는 각자의 시트에서 이어진다."""
    pid, ids = project
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases/bulk-clone", headers=auth(token),
                      json={"ids": [ids[("로그인", 1)], ids[("결제", 1)]]})
    assert r.status_code == 201, r.text
    got = {tc["sheet_name"]: tc["no"] for tc in r.json()}
    assert got == {"로그인": 4, "결제": 3}
    assert _nos_of(token, pid, "로그인") == [1, 2, 3, 4]
    assert _nos_of(token, pid, "결제") == [1, 2, 3]


def test_bulk_clone_same_sheet_increments(token, project):
    """같은 시트에서 두 건을 복제하면 번호가 겹치지 않는다."""
    pid, ids = project
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases/bulk-clone", headers=auth(token),
                      json={"ids": [ids[("결제", 1)], ids[("결제", 2)]]})
    assert r.status_code == 201, r.text
    assert sorted(tc["no"] for tc in r.json()) == [3, 4]
    assert _nos_of(token, pid, "결제") == [1, 2, 3, 4]


def test_clone_skips_numbers_held_by_deleted_tc(token, project):
    """지운 TC 가 쥐고 있던 번호는 복제가 다시 쓰지 않는다.

    삭제는 soft delete 라 되돌릴 수 있다. 살아 있는 TC 만 보고 번호를 주면,
    지운 뒤 복제하고 다시 되살렸을 때 같은 시트에 같은 번호가 둘이 된다.
    """
    pid, ids = project
    h = auth(token)
    victim = ids[("결제", 2)]  # no = 2

    assert requests.delete(f"{BASE}/api/projects/{pid}/testcases/{victim}",
                           headers=h).status_code in (200, 204)

    r = requests.post(f"{BASE}/api/projects/{pid}/testcases/{ids[('결제', 1)]}/clone", headers=h)
    assert r.status_code == 201, r.text
    cloned_no = r.json()["no"]
    assert cloned_no != 2, "지운 TC 의 번호를 다시 쓰면 복원할 때 겹친다"

    assert requests.post(f"{BASE}/api/projects/{pid}/testcases/{victim}/restore",
                         headers=h).status_code == 200
    assert _nos_of(token, pid, "결제") == sorted({1, 2, cloned_no})


def test_clone_ignores_other_sheets(token, project):
    """다른 시트의 큰 번호는 복제 번호에 영향을 주지 않는다."""
    pid, ids = project
    _add_tc(token, pid, 500, "TC-로그인-500", "로그인")

    r = requests.post(
        f"{BASE}/api/projects/{pid}/testcases/{ids[('결제', 1)]}/clone", headers=auth(token))
    assert r.status_code == 201, r.text
    assert r.json()["no"] == 3
