"""TC 칸 충돌 검사를 실제 HTTP 로 본다 (SYM-224)

라우트 함수를 직접 부르는 test_tc_edit_conflict.py 는 response_model 이 있는 라우트가
JSONResponse 409 를 그대로 내보내는지, 화면(axios)이 받는 본문 모양이 맞는지는 보지 못한다.

실행: cd backend && python -m pytest tests_unit/test_tc_edit_conflict_http.py -q
"""
import os
import sys

import pytest
import requests

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from auth import hash_password
from models import Project, ProjectMember, ProjectRole, TestCase, TestCaseSheet, User, UserRole

PW = "Passw0rd!long"
T = 10  # 서버가 멈춰도 CI 상한까지 매달리지 않게


@pytest.fixture
def env(auth_env):
    db = auth_env.Session()
    users = [User(username=n, password_hash=hash_password(PW), display_name=n, role=UserRole.user) for n in ("a", "b")]
    db.add_all(users)
    db.flush()
    p = Project(name="P", created_by=users[0].id, is_private=True)
    db.add(p)
    db.flush()
    for u in users:
        db.add(ProjectMember(project_id=p.id, user_id=u.id, role=ProjectRole.admin))
    db.add(TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False))
    tc = TestCase(project_id=p.id, no=1, tc_id="T-1", expected_result="원래", sheet_name="S", created_by=users[0].id)
    db.add(tc)
    db.commit()
    ids = (p.id, tc.id)
    db.close()
    yield auth_env.base, *ids


def _auth(base, username):
    r = requests.post(base + "/api/auth/login", json={"username": username, "password": PW}, timeout=T)
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_같은_칸을_옛_기준으로_고치면_409_와_서버_행을_준다(env):
    base, pid, tid = env
    url = f"{base}/api/projects/{pid}/testcases/{tid}"
    ha, hb = _auth(base, "a"), _auth(base, "b")

    r = requests.put(url, json={"expected_result": "B 값", "base_values": {"expected_result": "원래"}}, headers=hb, timeout=T)
    assert r.status_code == 200, r.text
    r = requests.put(url, json={"expected_result": "A 값", "base_values": {"expected_result": "원래"}}, headers=ha, timeout=T)
    assert r.status_code == 409, r.text
    body = r.json()
    assert body["conflicts"] == [{"id": tid, "fields": ["expected_result"]}]
    assert body["current"][0]["expected_result"] == "B 값"
    assert body["detail"].startswith("다른 사용자가 먼저 고친 칸이 있습니다: T-1")

    # 거절한 요청이 잠금을 쥐고 있지 않아 바로 다음 저장이 된다
    r = requests.put(url, json={"expected_result": "A 값", "base_values": {"expected_result": "B 값"}}, headers=ha, timeout=5)
    assert r.status_code == 200, r.text
    assert r.json()["expected_result"] == "A 값"


def test_커스텀_칸_기준값_형식이_틀리면_422(env):
    base, pid, tid = env
    r = requests.put(f"{base}/api/projects/{pid}/testcases/{tid}",
                     json={"custom_fields": {"x": "1"}, "base_values": {"custom_fields": "abc"}},
                     headers=_auth(base, "a"), timeout=T)
    assert r.status_code == 422, r.text
