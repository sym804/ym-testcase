"""배정 요청이 존재 확인을 통과한 뒤 그 계정이 지워지면 404 를 준다(SYM-164).

전에는 외래키 오류가 전역 핸들러로 가서 "데이터 제약 조건에 걸렸습니다"(409) 로 보였다.
경합은 커밋 직전에 다른 연결로 계정을 지워 결정적으로 만든다.
"""
import requests
from sqlalchemy import event, text

from auth_helpers import bearer, login, make_user
from models import Project, ProjectMember, UserRole


def _delete_user_before_commit(env, uid):
    """다음 커밋 한 번 직전에 다른 연결로 계정을 지운다."""
    fired = []

    def hook(session):
        if fired:
            return
        fired.append(True)
        with env.engine.begin() as conn:
            conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})

    event.listen(env.Session, "before_commit", hook)
    return lambda: event.remove(env.Session, "before_commit", hook)


def _project(env, owner):
    with env.Session() as s:
        p = Project(name="경합", created_by=owner)
        s.add(p)
        s.flush()
        s.add(ProjectMember(project_id=p.id, user_id=owner, role="admin"))
        s.commit()
        return p.id


def test_멤버_추가_중_계정이_지워지면_404(auth_env):
    boss = make_user(auth_env.Session, username="boss", role=UserRole.admin)
    target = make_user(auth_env.Session, username="target")
    pid = _project(auth_env, boss)
    h = bearer(login(auth_env.base, "boss"))

    undo = _delete_user_before_commit(auth_env, target)
    try:
        r = requests.post(auth_env.base + f"/api/projects/{pid}/members", headers=h,
                          json={"user_id": target, "role": "tester"})
    finally:
        undo()

    assert r.status_code == 404, r.text
    with auth_env.Session() as s:
        assert s.query(ProjectMember).filter_by(user_id=target).count() == 0


def test_전체_배정_중_계정이_지워지면_404(auth_env):
    boss = make_user(auth_env.Session, username="boss", role=UserRole.admin)
    target = make_user(auth_env.Session, username="target")
    _project(auth_env, boss)
    h = bearer(login(auth_env.base, "boss"))

    undo = _delete_user_before_commit(auth_env, target)
    try:
        r = requests.post(auth_env.base + "/api/projects/assign-all", headers=h,
                          json={"user_id": target, "role": "tester"})
    finally:
        undo()

    assert r.status_code == 404, r.text


def test_같은_사용자를_동시에_추가하면_두번째는_400(auth_env):
    """중복 확인을 통과한 두 요청 중 늦은 쪽은 유니크 제약에 걸린다. 이미 멤버라는 안내를 준다."""
    boss = make_user(auth_env.Session, username="boss", role=UserRole.admin)
    target = make_user(auth_env.Session, username="target")
    pid = _project(auth_env, boss)
    h = bearer(login(auth_env.base, "boss"))
    fired = []

    def hook(session):
        if fired:
            return
        fired.append(True)
        with auth_env.engine.begin() as conn:
            conn.execute(text("INSERT INTO project_members (project_id, user_id, role) "
                              "VALUES (:p, :u, 'tester')"), {"p": pid, "u": target})

    event.listen(auth_env.Session, "before_commit", hook)
    try:
        r = requests.post(auth_env.base + f"/api/projects/{pid}/members", headers=h,
                          json={"user_id": target, "role": "tester"})
    finally:
        event.remove(auth_env.Session, "before_commit", hook)

    assert r.status_code == 400, r.text
    assert "already" in r.json()["detail"]
