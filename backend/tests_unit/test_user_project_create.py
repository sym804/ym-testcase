"""로그인한 사용자는 시스템 역할과 무관하게 프로젝트를 만든다.

예전에는 qa_manager 이상만 만들 수 있어서, 팀원이 자기 업무용 프로젝트가 필요할 때마다
관리자에게 부탁해야 했다. 만든 사람은 그 프로젝트의 admin 멤버로 들어가고, 역할 판정은
멤버 표 하나로 한다(SYM-192 규칙 그대로).
"""
import requests

from auth_helpers import bearer, login, make_user
from models import ProjectMember, ProjectRole, UserRole


def test_일반_사용자가_프로젝트를_만들면_그_프로젝트의_admin_멤버가_된다(auth_env):
    uid = make_user(auth_env.Session, username="plain", role=UserRole.user)
    h = bearer(login(auth_env.base, "plain"))

    r = requests.post(auth_env.base + "/api/projects", headers=h, json={"name": "내 프로젝트", "is_private": True})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["my_role"] == "admin"

    with auth_env.Session() as s:
        m = s.query(ProjectMember).filter_by(project_id=pid, user_id=uid).one()
        assert m.role == ProjectRole.admin

    # 비공개라도 만든 사람은 목록에서 보고, 시트를 만들 수 있다(프로젝트 admin 권한)
    listed = {p["id"]: p["my_role"] for p in requests.get(auth_env.base + "/api/projects", headers=h).json()}
    assert listed[pid] == "admin"
    r = requests.post(auth_env.base + f"/api/projects/{pid}/testcases/sheets", headers=h, json={"name": "S1"})
    assert r.status_code == 200, r.text


def test_일반_사용자가_만든_비공개_프로젝트는_다른_일반_사용자에게_안_보인다(auth_env):
    make_user(auth_env.Session, username="maker", role=UserRole.user)
    make_user(auth_env.Session, username="stranger", role=UserRole.user)
    h = bearer(login(auth_env.base, "maker"))
    pid = requests.post(auth_env.base + "/api/projects", headers=h,
                        json={"name": "비밀", "is_private": True}).json()["id"]

    h2 = bearer(login(auth_env.base, "stranger"))
    assert pid not in [p["id"] for p in requests.get(auth_env.base + "/api/projects", headers=h2).json()]
    assert requests.get(auth_env.base + f"/api/projects/{pid}", headers=h2).status_code == 403


def test_로그인하지_않으면_프로젝트를_만들_수_없다(auth_env):
    r = requests.post(auth_env.base + "/api/projects", json={"name": "익명"})
    assert r.status_code == 401


def test_일반_사용자가_만든_프로젝트의_멤버_후보_목록은_최소_정보만_준다(auth_env):
    """누구나 자기 프로젝트의 admin 이 되므로, 멤버 후보 목록이 계정 관리 정보까지 주면
    가입만 하면 전체 사용자의 역할·상태·연결된 Google 이메일을 보게 된다."""
    from models import UserStatus
    make_user(auth_env.Session, username="host", role=UserRole.user)
    make_user(auth_env.Session, username="colleague", role=UserRole.qa_manager, google_email="c@corp.example")
    make_user(auth_env.Session, username="waiting", status=UserStatus.pending)
    make_user(auth_env.Session, username="stopped", status=UserStatus.disabled)
    h = bearer(login(auth_env.base, "host"))
    pid = requests.post(auth_env.base + "/api/projects", headers=h, json={"name": "팀"}).json()["id"]

    r = requests.get(auth_env.base + f"/api/projects/{pid}/members/available-users", headers=h)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert {row["username"] for row in rows} == {"colleague"}
    assert all(set(row) == {"id", "username", "display_name"} for row in rows)


def test_일반_사용자_프로젝트_admin_은_사용_중이_아닌_계정을_멤버로_넣을_수_없다(auth_env):
    """후보 목록에서 뺀 계정을 id 를 하나씩 넣어 보는 것으로 알아내지 못하게 한다.
    없는 계정과 같은 404 로 답해 존재 여부도 드러내지 않는다."""
    from models import UserStatus
    make_user(auth_env.Session, username="host2", role=UserRole.user)
    waiting = make_user(auth_env.Session, username="waiting2", status=UserStatus.pending)
    stopped = make_user(auth_env.Session, username="stopped2", status=UserStatus.disabled)
    active = make_user(auth_env.Session, username="active2")
    h = bearer(login(auth_env.base, "host2"))
    pid = requests.post(auth_env.base + "/api/projects", headers=h, json={"name": "팀2"}).json()["id"]

    def add(uid):
        return requests.post(auth_env.base + f"/api/projects/{pid}/members", headers=h,
                             json={"user_id": uid, "role": "tester"})

    missing = add(999999)
    for uid in (waiting, stopped):
        r = add(uid)
        assert r.status_code == 404, r.text
        assert r.json() == missing.json()
    assert add(active).status_code == 201


def test_시스템_관리자는_승인_대기_계정을_미리_멤버로_넣을_수_있다(auth_env):
    from models import UserStatus
    make_user(auth_env.Session, username="boss3", role=UserRole.qa_manager)
    waiting = make_user(auth_env.Session, username="waiting3", status=UserStatus.pending)
    h = bearer(login(auth_env.base, "boss3"))
    pid = requests.post(auth_env.base + "/api/projects", headers=h, json={"name": "팀3"}).json()["id"]
    r = requests.post(auth_env.base + f"/api/projects/{pid}/members", headers=h,
                      json={"user_id": waiting, "role": "tester"})
    assert r.status_code == 201, r.text
