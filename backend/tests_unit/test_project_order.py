"""사용자별 프로젝트 순서 (SYM-228)

- 순서를 정하지 않으면 만든 순서 최신순이다(예전과 같다).
- 저장한 순서는 메인 화면(overview)과 프로젝트 목록 API(상단 선택 목록)에 같이 적용된다.
- 순서는 사용자별이다. 다른 사람 화면은 그대로다.
- 순서를 정하지 않은 프로젝트(저장 뒤에 생긴 것, 보낸 목록에서 빠진 것)는 맨 위에 온다.
- 볼 수 없는 비공개 프로젝트와 없는 프로젝트는 같은 문구로 거절하고, 저장된 순서는 그대로다.
- 두 탭에서 동시에 저장해도 500 이 나지 않는다.
- 프로젝트를 지우면 순서 행도 지워진다.

실행: cd backend && python -m pytest tests_unit/test_project_order.py -q
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import requests
from sqlalchemy import event, text

from auth_helpers import bearer, login, make_user
from models import Project, ProjectMember, ProjectOrder, UserRole
from routes.projects import ORDER_DUPLICATE_DETAIL, ORDER_UNKNOWN_DETAIL

BASE = datetime(2026, 9, 1, 10, 0)


def _projects(env, owner, names, private=()):
    """names 순서대로 한 시간씩 늦게 만든다(마지막이 최신)."""
    ids = []
    with env.Session() as s:
        for i, name in enumerate(names):
            p = Project(name=name, created_by=owner, is_private=name in private,
                        created_at=BASE + timedelta(hours=i))
            s.add(p)
            s.flush()
            s.add(ProjectMember(project_id=p.id, user_id=owner, role="admin"))
            ids.append(p.id)
        s.commit()
    return ids


def _names_overview(env, h):
    r = requests.get(env.base + "/api/dashboard/overview", headers=h)
    assert r.status_code == 200, r.text
    return [p["name"] for p in r.json()["projects"]]


def _names_list(env, h):
    r = requests.get(env.base + "/api/projects", headers=h)
    assert r.status_code == 200, r.text
    return [p["name"] for p in r.json()]


def _save(env, h, ids):
    return requests.put(env.base + "/api/projects/order", headers=h, json={"project_ids": ids})


def _setup(env):
    ym = make_user(env.Session, username="ym")
    other = make_user(env.Session, username="other")
    a, b, c = _projects(env, ym, ["A", "B", "C"])
    return ym, other, (a, b, c), bearer(login(env.base, "ym")), bearer(login(env.base, "other"))


def test_순서가_없으면_최신순이다(auth_env):
    _, _, _, h, _ = _setup(auth_env)
    assert _names_overview(auth_env, h) == ["C", "B", "A"]
    assert _names_list(auth_env, h) == ["C", "B", "A"]


def test_저장한_순서가_메인_화면과_목록에_같이_적용된다(auth_env):
    _, _, (a, b, c), h, _ = _setup(auth_env)
    r = _save(auth_env, h, [a, c, b])
    assert r.status_code == 204, r.text
    assert _names_overview(auth_env, h) == ["A", "C", "B"]
    assert _names_list(auth_env, h) == ["A", "C", "B"]
    # 다시 저장하면 앞의 순서를 통째로 바꾼다
    assert _save(auth_env, h, [b, a, c]).status_code == 204
    assert _names_overview(auth_env, h) == ["B", "A", "C"]


def test_순서는_사용자별이다(auth_env):
    _, _, (a, b, c), h, h_other = _setup(auth_env)
    assert _save(auth_env, h, [a, b, c]).status_code == 204
    assert _names_overview(auth_env, h) == ["A", "B", "C"]
    assert _names_overview(auth_env, h_other) == ["C", "B", "A"]
    assert _save(auth_env, h_other, [b, c, a]).status_code == 204
    assert _names_overview(auth_env, h) == ["A", "B", "C"]
    assert _names_overview(auth_env, h_other) == ["B", "C", "A"]


def test_순서를_정하지_않은_프로젝트는_맨_위에_온다(auth_env):
    ym, _, (a, b, c), h, _ = _setup(auth_env)
    # 보낸 목록에서 빠진 C 는 순서가 없는 것으로 돌아간다
    assert _save(auth_env, h, [a, b]).status_code == 204
    assert _names_overview(auth_env, h) == ["C", "A", "B"]
    # 저장 뒤에 생긴 프로젝트는 그보다 위(둘 다 순서 없음, 최신순)
    _projects(auth_env, ym, ["D"])
    with auth_env.Session() as s:
        s.query(Project).filter_by(name="D").update({"created_at": BASE + timedelta(days=1)})
        s.commit()
    assert _names_overview(auth_env, h) == ["D", "C", "A", "B"]


def test_볼_수_없는_프로젝트와_없는_프로젝트는_같은_문구로_거절한다(auth_env):
    ym, other, (a, b, c), h, h_other = _setup(auth_env)
    (secret,) = _projects(auth_env, ym, ["S"], private={"S"})
    assert _save(auth_env, h_other, [a, b]).status_code == 204
    for ids in ([secret, a, b, c], [a, b, c, 999999]):
        r = _save(auth_env, h_other, ids)
        assert (r.status_code, r.json()["detail"]) == (400, ORDER_UNKNOWN_DETAIL), r.text
    with auth_env.Session() as s:
        rows = s.query(ProjectOrder).filter_by(user_id=other).order_by(ProjectOrder.position).all()
        assert [x.project_id for x in rows] == [a, b], "거절하면 저장된 순서를 건드리지 않는다"
    # 멤버는 자기 비공개 프로젝트를 옮긴다
    assert _save(auth_env, h, [secret, a, b, c]).status_code == 204
    assert _names_overview(auth_env, h)[0] == "S"


def test_같은_프로젝트를_두_번_보내면_거절한다(auth_env):
    _, _, (a, b, c), h, _ = _setup(auth_env)
    r = _save(auth_env, h, [a, b, a])
    assert (r.status_code, r.json()["detail"]) == (400, ORDER_DUPLICATE_DETAIL), r.text


def test_관리자는_멤버가_아닌_비공개_프로젝트도_옮긴다(auth_env):
    ym, _, (a, b, c), _, _ = _setup(auth_env)
    (secret,) = _projects(auth_env, ym, ["S"], private={"S"})
    make_user(auth_env.Session, username="boss", role=UserRole.admin)
    h_boss = bearer(login(auth_env.base, "boss"))
    assert _save(auth_env, h_boss, [a, secret, b, c]).status_code == 204
    assert _names_overview(auth_env, h_boss) == ["A", "S", "B", "C"]


def test_동시에_저장해도_500_이_나지_않는다(auth_env):
    ym, _, ids, h, _ = _setup(auth_env)
    more = _projects(auth_env, ym, [f"P{i}" for i in range(20)])
    all_ids = list(ids) + more
    orders = [all_ids[i:] + all_ids[:i] for i in range(8)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        codes = list(ex.map(lambda o: _save(auth_env, h, o).status_code, orders))
    assert codes == [204] * 8, codes
    with auth_env.Session() as s:
        rows = s.query(ProjectOrder).filter_by(user_id=ym).order_by(ProjectOrder.position).all()
        got = [x.project_id for x in rows]
    assert got in orders, "마지막으로 저장한 한 요청의 순서가 통째로 남는다(섞이지 않는다)"


def test_프로젝트를_지우면_순서_행도_지워진다(auth_env):
    ym, _, (a, b, c), h, _ = _setup(auth_env)
    assert _save(auth_env, h, [a, b, c]).status_code == 204
    r = requests.delete(f"{auth_env.base}/api/projects/{b}", headers=h)
    assert r.status_code == 204, r.text
    with auth_env.Session() as s:
        assert [x.project_id for x in s.query(ProjectOrder).order_by(ProjectOrder.position)] == [a, c]
    assert _names_overview(auth_env, h) == ["A", "C"]


def test_저장_중에_프로젝트가_지워지면_새로고침_안내로_거절한다(auth_env):
    """가시성 확인을 통과한 뒤 다른 연결이 프로젝트를 지우면 외래키 오류가 난다(QA1 지적).
    전역 처리기의 "데이터 제약 조건에 걸렸습니다."(409) 대신 새로고침 안내를 준다."""
    ym, _, (a, b, c), h, _ = _setup(auth_env)
    # b 에는 순서 행을 두지 않는다. 있으면 요청이 지운(잠근) 그 행을 다른 연결의 CASCADE 가
    # 기다리고, 요청은 훅이 끝나기를 기다려 테스트가 멈춘다(운영에서는 생기지 않는 교착).
    assert _save(auth_env, h, [a, c]).status_code == 204
    fired = []

    def hook(session):
        if fired:
            return
        fired.append(True)
        with auth_env.engine.begin() as conn:
            conn.execute(text("DELETE FROM projects WHERE id = :id"), {"id": b})

    event.listen(auth_env.Session, "before_commit", hook)
    try:
        r = _save(auth_env, h, [c, b, a])
    finally:
        event.remove(auth_env.Session, "before_commit", hook)
    assert fired, "경합을 만들지 못했다"
    assert (r.status_code, r.json()["detail"]) == (400, ORDER_UNKNOWN_DETAIL), r.text
    with auth_env.Session() as s:
        rows = s.query(ProjectOrder).filter_by(user_id=ym).order_by(ProjectOrder.position).all()
        assert [x.project_id for x in rows] == [a, c], "실패하면 앞의 순서가 그대로 남는다"


def test_빈_목록을_보내면_순서를_모두_지운다(auth_env):
    ym, _, (a, b, c), h, _ = _setup(auth_env)
    assert _save(auth_env, h, [a, b, c]).status_code == 204
    assert _save(auth_env, h, []).status_code == 204
    assert _names_overview(auth_env, h) == ["C", "B", "A"]


def test_2000개를_넘으면_거절한다(auth_env):
    _, _, _, h, _ = _setup(auth_env)
    assert _save(auth_env, h, list(range(1, 2002))).status_code == 422
