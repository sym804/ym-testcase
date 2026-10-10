"""큰 JSON 응답은 압축해 보낸다. Vercel 함수 응답 상한(4.5MB)을 넘지 않게 하려는 것이다."""
import requests

from auth_helpers import bearer, login, make_user
from models import Project, ProjectMember, TestCase, UserRole


def test_큰_목록_응답은_gzip(auth_env):
    boss = make_user(auth_env.Session, username="boss", role=UserRole.admin)
    with auth_env.Session() as s:
        p = Project(name="압축", created_by=boss)
        s.add(p)
        s.flush()
        s.add(ProjectMember(project_id=p.id, user_id=boss, role="admin"))
        for i in range(1, 51):
            s.add(TestCase(project_id=p.id, sheet_name="기본", no=i, tc_id=f"TC-{i:03d}",
                           test_steps="절차 " * 40, created_by=boss))
        s.commit()
        pid = p.id
    h = bearer(login(auth_env.base, "boss"))

    r = requests.get(auth_env.base + f"/api/projects/{pid}/testcases",
                     headers={**h, "Accept-Encoding": "gzip"})

    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
    assert len(r.json()) == 50
