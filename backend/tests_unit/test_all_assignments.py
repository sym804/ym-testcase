"""관리 화면의 '프로젝트 배정' 칸이 쓰는 전체 배정 조회.

/api/projects/{project_id} 가 먼저 등록돼 있으면 all-assignments 를 프로젝트 번호로 읽어
422 를 낸다. 화면은 실패를 삼키고 모든 사용자를 '미배정' 으로 보였다(v0.7.0 부터).
"""
import re
from collections import Counter

import requests

from auth_helpers import bearer, login, make_user
from models import Project, ProjectMember, ProjectRole, UserRole


def test_전체_배정_조회는_멤버를_사용자별로_준다(auth_env):
    boss = make_user(auth_env.Session, username="boss", role=UserRole.admin)
    uid = make_user(auth_env.Session, username="member1")
    with auth_env.Session() as s:
        p = Project(name="배정 확인", created_by=boss)
        s.add(p)
        s.flush()
        s.add(ProjectMember(project_id=p.id, user_id=uid, role=ProjectRole.tester))
        s.commit()
        pid = p.id
        mid = s.query(ProjectMember).filter_by(user_id=uid).one().id
    h = bearer(login(auth_env.base, "boss"))

    r = requests.get(auth_env.base + "/api/projects/all-assignments", headers=h)

    assert r.status_code == 200, r.text
    assert r.json()[str(uid)] == [
        {"id": mid, "project_id": pid, "project_name": "배정 확인", "role": "tester"}
    ]
    # 같은 접두사의 프로젝트 단건 조회는 그대로 동작한다
    assert requests.get(auth_env.base + f"/api/projects/{pid}", headers=h).status_code == 200



def _sample(path: str) -> str:
    """경로 변수 칸을 실제 요청처럼 채운 주소."""
    return re.sub(r"\{[^}]+\}", "1", path)


def test_앞서_등록된_경로가_뒤의_경로를_가리지_않는다():
    """앞 라우트의 실제 정규식(path_regex)이 뒤 라우트로 가야 할 주소를 먼저 잡는지 본다.

    글자 비교가 아니라 Starlette 가 쓰는 정규식으로 판정해 {x:path} 같은 변환자도 맞게 다룬다.
    """
    from main import app

    routes = [r for r in app.routes if hasattr(r, "methods") and hasattr(r, "path_regex")]
    hidden = [f"{m} {early.path} -> {late.path}"
              for i, early in enumerate(routes)
              for late in routes[i + 1:]
              for m in early.methods & late.methods
              if early.path != late.path and early.path_regex.fullmatch(_sample(late.path))]
    assert hidden == []
    # 같은 경로와 메서드를 두 번 등록하면 뒤 라우트는 영영 불리지 않는다
    seen = Counter((m, r.path) for r in routes for m in r.methods)
    assert [k for k, n in seen.items() if n > 1] == []


def test_정규식_판정은_변환자와_섞인_칸을_구분한다():
    """위 점검의 판정 규칙 자체를 확인한다(거짓 음성, 거짓 양성)."""
    from starlette.routing import Route

    def shadows(early, late):
        return bool(Route(early, endpoint=lambda r: None).path_regex.fullmatch(_sample(late)))

    assert shadows("/p/{project_id}", "/p/all-assignments")
    assert shadows("/files/{x:path}", "/files/a/b")
    assert shadows("/files/prefix-{x}", "/files/prefix-export")
    assert shadows("/a/{x}/{y}", "/a/fixed/{z}")
    assert not shadows("/items/{x:int}", "/items/export")
    assert not shadows("/p/{project_id}/members", "/p/all-assignments")


def test_전체_배정_조회와_일괄_배정은_qa_manager_이상만(auth_env):
    make_user(auth_env.Session, username="plain")
    h = bearer(login(auth_env.base, "plain"))
    assert requests.get(auth_env.base + "/api/projects/all-assignments").status_code == 401
    assert requests.get(auth_env.base + "/api/projects/all-assignments", headers=h).status_code == 403
    assert requests.post(auth_env.base + "/api/projects/assign-all", headers=h,
                         json={"user_id": 1, "role": "tester"}).status_code == 403
