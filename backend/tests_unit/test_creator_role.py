"""프로젝트 역할은 멤버 표 하나로 정한다. 생성자라는 이유만으로 admin 을 주지 않는다.

생성자는 만들 때 admin 멤버로 자동 등록된다. 그런데 역할 판정이 created_by 를 따로 보고 있어서,
qa_manager 가 강등된 뒤 관리자가 그 사람의 멤버 역할을 낮추거나 빼도 계속 admin 이었다
(프로젝트 삭제, 멤버 관리 가능). 생성자는 멤버에서 뺄 수도 없었다.
"""
import requests

from auth_helpers import bearer, login, make_user
from models import Project, ProjectMember, ProjectRole, User, UserRole


def _setup(env):
    boss = make_user(env.Session, username="boss", role=UserRole.admin)
    owner = make_user(env.Session, username="owner", role=UserRole.qa_manager)
    h_owner = bearer(login(env.base, "owner"))
    r = requests.post(env.base + "/api/projects", headers=h_owner, json={"name": "비공개", "is_private": True})
    assert r.status_code in (200, 201), r.text
    pid = r.json()["id"]
    # 강등
    with env.Session() as s:
        s.get(User, owner).role = UserRole.user
        s.commit()
    return boss, owner, pid


def _member(env, pid, uid):
    with env.Session() as s:
        return s.query(ProjectMember).filter_by(project_id=pid, user_id=uid).one()


def test_강등된_생성자의_멤버_역할을_낮추면_그_역할을_따른다(auth_env):
    boss, owner, pid = _setup(auth_env)
    h_boss = bearer(login(auth_env.base, "boss"))
    m = _member(auth_env, pid, owner)
    r = requests.put(auth_env.base + f"/api/projects/{pid}/members/{m.id}", headers=h_boss, json={"role": "tester"})
    assert r.status_code == 200, r.text

    h_owner = bearer(login(auth_env.base, "owner"))
    assert requests.delete(auth_env.base + f"/api/projects/{pid}", headers=h_owner).status_code == 403
    listed = {p["id"]: p["my_role"] for p in requests.get(auth_env.base + "/api/projects", headers=h_owner).json()}
    assert listed[pid] == "tester"


def test_시스템_관리자는_생성자를_멤버에서_뺄_수_있고_비공개면_접근이_끊긴다(auth_env):
    boss, owner, pid = _setup(auth_env)
    h_boss = bearer(login(auth_env.base, "boss"))
    m = _member(auth_env, pid, owner)
    r = requests.delete(auth_env.base + f"/api/projects/{pid}/members/{m.id}", headers=h_boss)
    assert r.status_code == 204, r.text

    h_owner = bearer(login(auth_env.base, "owner"))
    assert requests.get(auth_env.base + f"/api/projects/{pid}", headers=h_owner).status_code == 403
    assert pid not in [p["id"] for p in requests.get(auth_env.base + "/api/projects", headers=h_owner).json()]
    assert requests.get(auth_env.base + "/api/search", headers=h_owner, params={"q": "x"}).status_code == 200


def test_프로젝트_admin_멤버는_생성자를_뺄_수_없다(auth_env):
    """생성자 보호는 프로젝트 안 관리자끼리의 다툼을 막는 것이라 남긴다. 시스템 관리자만 뺀다."""
    boss, owner, pid = _setup(auth_env)
    other = make_user(auth_env.Session, username="other")
    with auth_env.Session() as s:
        s.add(ProjectMember(project_id=pid, user_id=other, role=ProjectRole.admin))
        s.commit()
    h_other = bearer(login(auth_env.base, "other"))
    m = _member(auth_env, pid, owner)
    r = requests.delete(auth_env.base + f"/api/projects/{pid}/members/{m.id}", headers=h_other)
    assert r.status_code == 400, r.text


def test_프로젝트_admin_멤버는_생성자의_역할도_바꿀_수_없다(auth_env):
    """제거와 같은 규칙. 화면만 막고 서버가 받으면 API 로 생성자를 강등할 수 있다."""
    boss, owner, pid = _setup(auth_env)
    other = make_user(auth_env.Session, username="other2")
    with auth_env.Session() as s:
        s.add(ProjectMember(project_id=pid, user_id=other, role=ProjectRole.admin))
        s.commit()
    h_other = bearer(login(auth_env.base, "other2"))
    m = _member(auth_env, pid, owner)
    r = requests.put(auth_env.base + f"/api/projects/{pid}/members/{m.id}", headers=h_other, json={"role": "tester"})
    assert r.status_code == 400, r.text
    assert _member(auth_env, pid, owner).role == ProjectRole.admin
