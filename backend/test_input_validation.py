"""입력 검증 - 만들 때는 막고 고칠 때는 통과하던 자리

같은 값을 생성에서는 거부하는데 수정에서는 받아 주면, 검증이 있다는 사실이
오히려 잘못된 안심을 준다. 커스텀 필드 타입이 그랬다(생성 400, 수정 200).

실행: cd backend && TEST_PORT=8099 TEST_BASE_URL=http://127.0.0.1:8099 python -m pytest test_input_validation.py -v
"""
import os

import pytest
import requests

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
    r = requests.post(f"{BASE}/api/projects", headers=h, json={"name": "__validation__"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    requests.post(f"{BASE}/api/projects/{pid}/testcases/sheets", headers=h,
                  json={"name": "기본", "parent_id": None, "is_folder": False})
    yield pid
    requests.delete(f"{BASE}/api/projects/{pid}", headers=h)


def _add_tc(token, pid, no=1, tc_id="TC-001"):
    r = requests.post(f"{BASE}/api/projects/{pid}/testcases", headers=auth(token), json={
        "no": no, "tc_id": tc_id, "category": "기본", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ── 커스텀 필드 ───────────────────────────────────────────────────────────────

def test_커스텀필드_수정도_타입을_검증한다(token, project):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/custom-fields", headers=h,
                      json={"field_name": "환경", "field_type": "text"})
    assert r.status_code == 201, r.text
    fid = r.json()["id"]

    bad = requests.put(f"{BASE}/api/projects/{project}/custom-fields/{fid}", headers=h,
                       json={"field_type": "EVIL_TYPE"})
    assert bad.status_code == 400, f"수정으로 임의 타입이 저장됐다: {bad.status_code} {bad.text}"

    still = requests.get(f"{BASE}/api/projects/{project}/custom-fields", headers=h)
    assert still.json()[0]["field_type"] == "text"


def test_커스텀필드_수정은_허용된_타입을_받는다(token, project):
    h = auth(token)
    r = requests.post(f"{BASE}/api/projects/{project}/custom-fields", headers=h,
                      json={"field_name": "환경2", "field_type": "text"})
    fid = r.json()["id"]

    ok = requests.put(f"{BASE}/api/projects/{project}/custom-fields/{fid}", headers=h,
                      json={"field_type": "select", "options": ["A", "B"]})
    assert ok.status_code == 200, ok.text
    assert ok.json()["field_type"] == "select"


# ── 벌크 삭제 ─────────────────────────────────────────────────────────────────

def test_벌크삭제의_잘못된_ids는_400이다(token, project):
    """숫자가 아닌 값이 오면 500 이 아니라 400 이어야 한다."""
    r = requests.delete(f"{BASE}/api/projects/{project}/testcases/bulk?ids=abc",
                        headers=auth(token))
    assert r.status_code == 400, f"서버 오류로 샜다: {r.status_code} {r.text}"


def test_벌크삭제는_정상_ids를_처리한다(token, project):
    tc1 = _add_tc(token, project, 1, "TC-B01")
    tc2 = _add_tc(token, project, 2, "TC-B02")

    r = requests.delete(f"{BASE}/api/projects/{project}/testcases/bulk?ids={tc1},{tc2}",
                        headers=auth(token))
    assert r.status_code == 200, r.text


# ── 삭제된 TC ─────────────────────────────────────────────────────────────────

def test_삭제된_TC는_수정할_수_없다(token, project):
    """지운 TC 를 고칠 수 있으면 삭제와 복원의 의미가 흔들린다."""
    tc = _add_tc(token, project, 1, "TC-D01")
    d = requests.delete(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=auth(token))
    assert d.status_code in (200, 204), d.text

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=auth(token),
                     json={"category": "바뀐값"})
    assert r.status_code == 404, f"삭제된 TC 가 수정됐다: {r.status_code} {r.text}"


def test_살아있는_TC는_수정할_수_있다(token, project):
    tc = _add_tc(token, project, 1, "TC-D02")
    r = requests.put(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=auth(token),
                     json={"category": "바뀐값"})
    assert r.status_code == 200, r.text
    assert r.json()["category"] == "바뀐값"


# ── TC ID ─────────────────────────────────────────────────────────────────────

def test_빈_TC_ID는_거부한다(token, project):
    """빈 값은 사전조건 참조 색인에서 어느 TC 도 가리키지 못한다."""
    r = requests.post(f"{BASE}/api/projects/{project}/testcases", headers=auth(token), json={
        "no": 1, "tc_id": "", "category": "기본", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
    })
    assert r.status_code == 422, f"빈 TC ID 가 저장됐다: {r.status_code}"


def test_너무_긴_TC_ID는_거부한다(token, project):
    """컬럼은 50자인데 SQLite 는 길이를 강제하지 않아 그대로 들어간다.

    PostgreSQL 로 옮기면 그때 터지고, 그 사이에 쌓인 데이터는 옮길 수 없다.
    """
    r = requests.post(f"{BASE}/api/projects/{project}/testcases", headers=auth(token), json={
        "no": 1, "tc_id": "T" * 60, "category": "기본", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
    })
    assert r.status_code == 422, f"50자를 넘는 TC ID 가 저장됐다: {r.status_code}"


def test_정상_TC_ID는_받는다(token, project):
    r = requests.post(f"{BASE}/api/projects/{project}/testcases", headers=auth(token), json={
        "no": 1, "tc_id": "TC-OK-001", "category": "기본", "test_steps": "1. 실행",
        "expected_result": "성공", "sheet_name": "기본", "priority": "보통",
    })
    assert r.status_code == 201, r.text


# ── 시트 이름 ─────────────────────────────────────────────────────────────────

def test_번호가_겹치는_이름으로_바꾸면_이유를_알려_준다(token, project):
    """★시트를 지워도 TC 의 sheet_name 은 남고, 복원하면 활성 TC 로 돌아온다.

    그 이름으로 다른 시트를 바꾸면 (프로젝트, 시트명, 번호)가 겹쳐 유니크 제약에
    걸린다. 종전에는 전역 핸들러가 "데이터 제약 조건에 걸렸습니다" 라는 409 만
    내서 무엇을 어떻게 고쳐야 하는지 알 수 없었다.

    미리 "그 이름을 쓰는 TC 가 있으면 거절" 로 막지는 않는다. 번호가 겹치지 않으면
    실제로는 부딪히지 않아서, 막으면 멀쩡한 이름 변경까지 400 이 된다.
    """
    h = auth(token)
    # 시트 A: TC 1번
    rs = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                       json={"name": "결제", "parent_id": None, "is_folder": False})
    assert rs.status_code in (200, 201), rs.text
    tc_a = _add_tc(token, project, 1, "TC-PAY-001")
    requests.put(f"{BASE}/api/projects/{project}/testcases/{tc_a}", headers=h,
                 json={"sheet_name": "결제"})

    # 시트 A 를 지우면 그 TC 는 소프트 삭제된다. 복원해 활성으로 되돌린다.
    d = requests.delete(f"{BASE}/api/projects/{project}/testcases/sheets/결제", headers=h)
    assert d.status_code in (200, 204), d.text
    restored = requests.post(f"{BASE}/api/projects/{project}/testcases/{tc_a}/restore", headers=h)
    assert restored.status_code == 200, restored.text

    # 시트 B 에도 TC 를 둔다. 같은 번호라야 실제로 부딪힌다.
    rs2 = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                        json={"name": "임시", "parent_id": None, "is_folder": False})
    assert rs2.status_code in (200, 201), rs2.text
    other_id = rs2.json()["id"]
    tc_b = _add_tc(token, project, 2, "TC-TMP-001")
    requests.put(f"{BASE}/api/projects/{project}/testcases/{tc_b}", headers=h,
                 json={"sheet_name": "임시"})

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/sheets/{other_id}/rename",
                     headers=h, json={"new_name": "결제"})
    assert r.status_code == 400, (
        f"이유를 알 수 없는 실패 대신 400 으로 알려야 한다: {r.status_code} {r.text}"
    )
    assert "번호가 겹칩니다" in r.text, f"무엇이 문제인지 적혀 있지 않다: {r.text}"


def test_부딪히지_않는_이름_변경은_막지_않는다(token, project):
    """지운 TC 가 그 이름을 쓰고 있어도 번호가 겹치지 않으면 통과해야 한다."""
    h = auth(token)
    rs = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                       json={"name": "보관", "parent_id": None, "is_folder": False})
    assert rs.status_code in (200, 201), rs.text
    tc = _add_tc(token, project, 1, "TC-ARC-001")
    requests.put(f"{BASE}/api/projects/{project}/testcases/{tc}", headers=h,
                 json={"sheet_name": "보관"})
    requests.delete(f"{BASE}/api/projects/{project}/testcases/sheets/보관", headers=h)

    # 빈 시트를 그 이름으로 바꾼다. 옮길 TC 가 없으니 부딪히지 않는다.
    rs2 = requests.post(f"{BASE}/api/projects/{project}/testcases/sheets", headers=h,
                        json={"name": "빈시트", "parent_id": None, "is_folder": False})
    other_id = rs2.json()["id"]

    r = requests.put(f"{BASE}/api/projects/{project}/testcases/sheets/{other_id}/rename",
                     headers=h, json={"new_name": "보관"})
    assert r.status_code == 200, f"부딪히지 않는데 막았다: {r.status_code} {r.text}"
