"""대시보드 날짜 파라미터가 형식에 맞지 않으면 500 이 아니라 400 이다

실행: cd backend && python -m pytest tests_unit/test_dashboard_date_params.py -q
"""
import pytest
import requests

from auth_helpers import bearer, login, make_user
from models import UserRole

PATHS = ["summary", "priority", "category", "rounds", "assignee", "heatmap", "stability"]
#: assignee 는 v1.2.0 이후 날짜를 쓰지 않고 늘 빈 배열이다(라우트만 남김).
DATED = [p for p in PATHS if p != "assignee"]


@pytest.fixture
def admin(auth_env):
    make_user(auth_env.Session, username="root", role=UserRole.admin)
    h = bearer(login(auth_env.base, "root"))
    r = requests.post(auth_env.base + "/api/projects", json={"name": "P"}, headers=h)
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]
    # TC 가 있어야 우선순위 · 카테고리 집계가 날짜를 쓰는 데까지 간다.
    r = requests.post(f"{auth_env.base}/api/projects/{pid}/testcases",
                      json={"tc_id": "A-1", "priority": "High", "category": "c"}, headers=h)
    assert r.status_code == 201, r.text
    return auth_env.base, h, pid


@pytest.mark.parametrize("params", [{"date_from": "2026-13-45"}, {"date_to": "어제"},
                                    {"date_to": "2026-10-01T00:00"}])
@pytest.mark.parametrize("path", DATED)
def test_잘못된_날짜는_400(admin, path, params):
    base, h, pid = admin
    r = requests.get(f"{base}/api/projects/{pid}/dashboard/{path}", params=params, headers=h)
    assert r.status_code == 400, (path, r.status_code, r.text)
    assert "YYYY-MM-DD" in r.json()["detail"]


@pytest.mark.parametrize("path", PATHS)
def test_올바른_날짜는_그대로_된다(admin, path):
    base, h, pid = admin
    r = requests.get(f"{base}/api/projects/{pid}/dashboard/{path}",
                     params={"date_from": "2026-01-01", "date_to": "2026-12-31"}, headers=h)
    assert r.status_code == 200, (path, r.text)
