"""TC 칸 단위 충돌 검사 (SYM-224)

- 화면이 본 값(base_values)을 같이 보내면, 고친 칸의 서버 값이 그 사이 바뀌었는지 본다.
  바뀌었으면 409 와 서버의 현재 행을 돌려주고 아무것도 저장하지 않는다.
- 서로 다른 칸을 고친 것은 둘 다 저장된다. 커스텀 칸도 키 단위로 본다.
- base_values 를 보내지 않으면 예전처럼 저장한다(스크립트 · API 키 호환).
- 409 는 잠금을 풀고 돌려준다. 시트를 옮길 수 있는 요청은 프로젝트 잠금을 행 잠금보다 먼저 잡는다.

실행: cd backend && python -m pytest tests_unit/test_tc_edit_conflict.py -q
"""
import json
import os
import sys
import threading
import time

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from fastapi.responses import JSONResponse
from sqlalchemy.orm import sessionmaker

from models import Project, TestCase, TestCaseHistory, TestCaseSheet, User
from routes.testcases import bulk_update_testcases, update_testcase
from schemas import TestCaseBulkItem, TestCaseBulkUpdate, TestCaseUpdate


@pytest.fixture
def env(pg_engine):
    db = sessionmaker(bind=pg_engine)()
    a = User(username="a", password_hash="x", display_name="A", role="admin")
    b = User(username="b", password_hash="x", display_name="B", role="admin")
    db.add_all([a, b])
    db.flush()
    project = Project(name="P", created_by=a.id)
    db.add(project)
    db.flush()
    db.add(TestCaseSheet(project_id=project.id, name="S", sort_order=0, is_folder=False))
    tcs = []
    for n in (1, 2):
        tc = TestCase(project_id=project.id, no=n, tc_id=f"T-{n}", expected_result="원래",
                      remarks=None, sheet_name="S", created_by=a.id,
                      custom_fields={"x": "x0", "y": "y0"})
        db.add(tc)
        tcs.append(tc)
    db.commit()
    yield db, project, tcs, a, b
    db.close()


def _put(env, user, tc, **kw):
    db, project, _, _, _ = env
    return update_testcase(project.id, tc.id, TestCaseUpdate(**kw), db=db, current_user=user)


def _reload(db, tc):
    db.expire_all()
    return db.get(TestCase, tc.id)


def _body(resp):
    assert isinstance(resp, JSONResponse), f"409 응답이어야 한다: {resp!r}"
    assert resp.status_code == 409
    return json.loads(resp.body)


def test_본_값이_서버와_다르면_409_이고_앞의_값이_남는다(env):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], expected_result="B 값", base_values={"expected_result": "원래"})
    resp = _put(env, a, tcs[0], expected_result="A 값", base_values={"expected_result": "원래"})
    body = _body(resp)
    assert "T-1" in body["detail"] and "기대 결과" in body["detail"]
    assert body["conflicts"] == [{"id": tcs[0].id, "fields": ["expected_result"]}]
    assert body["current"][0]["expected_result"] == "B 값", "화면이 다시 그릴 서버 값을 준다"
    assert _reload(db, tcs[0]).expected_result == "B 값"


def test_거절된_저장은_변경_이력도_남기지_않는다(env):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], expected_result="B 값", base_values={"expected_result": "원래"})
    before = db.query(TestCaseHistory).count()
    _put(env, a, tcs[0], expected_result="A 값", remarks="비고", base_values={"expected_result": "원래", "remarks": None})
    db.expire_all()
    assert db.query(TestCaseHistory).count() == before
    assert _reload(db, tcs[0]).remarks is None, "같은 요청의 다른 칸도 저장하지 않는다"


def test_서로_다른_칸은_둘_다_저장된다(env):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], remarks="B 비고", base_values={"remarks": None})
    resp = _put(env, a, tcs[0], expected_result="A 값", base_values={"expected_result": "원래"})
    assert not isinstance(resp, JSONResponse)
    tc = _reload(db, tcs[0])
    assert (tc.expected_result, tc.remarks) == ("A 값", "B 비고")


def test_같은_값으로_고친_것은_충돌이_아니다(env):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], expected_result="같음", base_values={"expected_result": "원래"})
    resp = _put(env, a, tcs[0], expected_result="같음", base_values={"expected_result": "원래"})
    assert not isinstance(resp, JSONResponse)


def test_빈_문자열과_None_은_같은_값으로_본다(env):
    db, _, tcs, a, _ = env
    resp = _put(env, a, tcs[0], remarks="새 비고", base_values={"remarks": ""})
    assert not isinstance(resp, JSONResponse)
    assert _reload(db, tcs[0]).remarks == "새 비고"


def test_base_values_가_없으면_예전처럼_저장한다(env):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], expected_result="B 값", base_values={"expected_result": "원래"})
    resp = _put(env, a, tcs[0], expected_result="스크립트 값")
    assert not isinstance(resp, JSONResponse)
    assert _reload(db, tcs[0]).expected_result == "스크립트 값"


def test_커스텀_칸은_키마다_본다_다른_키는_둘_다_남는다(env):
    db, _, tcs, a, b = env
    base = {"x": "x0", "y": "y0"}
    _put(env, b, tcs[0], custom_fields={"x": "xB", "y": "y0"}, base_values={"custom_fields": base})
    resp = _put(env, a, tcs[0], custom_fields={"x": "x0", "y": "yA"}, base_values={"custom_fields": base})
    assert not isinstance(resp, JSONResponse)
    assert _reload(db, tcs[0]).custom_fields == {"x": "xB", "y": "yA"}, "A 의 옛 x 가 B 의 값을 되돌리면 안 된다"


def test_커스텀_칸의_같은_키는_충돌이다(env):
    db, _, tcs, a, b = env
    base = {"x": "x0", "y": "y0"}
    _put(env, b, tcs[0], custom_fields={"x": "xB", "y": "y0"}, base_values={"custom_fields": base})
    body = _body(_put(env, a, tcs[0], custom_fields={"x": "xA", "y": "y0"}, base_values={"custom_fields": base}))
    assert body["conflicts"][0]["fields"] == ["custom_fields.x"]
    assert _reload(db, tcs[0]).custom_fields["x"] == "xB"


def test_커스텀_칸에서_지운_키는_지워진다(env):
    db, _, tcs, a, _ = env
    resp = _put(env, a, tcs[0], custom_fields={"x": "x0"}, base_values={"custom_fields": {"x": "x0", "y": "y0"}})
    assert not isinstance(resp, JSONResponse)
    assert _reload(db, tcs[0]).custom_fields == {"x": "x0"}


def test_일괄_수정도_하나라도_어긋나면_전부_저장하지_않는다(env):
    db, project, tcs, a, b = env
    _put(env, b, tcs[1], expected_result="B 값", base_values={"expected_result": "원래"})
    resp = bulk_update_testcases(project.id, TestCaseBulkUpdate(items=[
        TestCaseBulkItem(id=tcs[0].id, expected_result="A1", base_values={"expected_result": "원래"}),
        TestCaseBulkItem(id=tcs[1].id, expected_result="A2", base_values={"expected_result": "원래"}),
    ]), db=db, current_user=a)
    body = _body(resp)
    assert [c["id"] for c in body["conflicts"]] == [tcs[1].id]
    assert _reload(db, tcs[0]).expected_result == "원래"
    assert _reload(db, tcs[1]).expected_result == "B 값"


def test_같은_기준값으로_동시에_저장하면_하나만_성공한다(pg_engine):
    n = 6
    s = sessionmaker(bind=pg_engine)()
    users = [User(username=f"u{i}", password_hash="x", display_name=f"U{i}", role="admin") for i in range(n)]
    s.add_all(users)
    s.flush()
    p = Project(name="P", created_by=users[0].id)
    s.add(p)
    s.flush()
    s.add(TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False))
    tc = TestCase(project_id=p.id, no=1, tc_id="T-1", expected_result="원래", sheet_name="S", created_by=users[0].id)
    s.add(tc)
    s.commit()
    pid, tid, uids = p.id, tc.id, [u.id for u in users]
    s.close()

    Session = sessionmaker(bind=pg_engine)
    barrier = threading.Barrier(n)
    outcomes = []

    def save(i):
        db = Session()
        try:
            user = db.get(User, uids[i])
            barrier.wait()
            resp = update_testcase(pid, tid, TestCaseUpdate(expected_result=f"값{i}", base_values={"expected_result": "원래"}),
                                   db=db, current_user=user)
            outcomes.append(resp.status_code if isinstance(resp, JSONResponse) else 200)
        finally:
            db.close()

    threads = [threading.Thread(target=save, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(outcomes) == [200] + [409] * (n - 1), outcomes


def test_일괄_수정에_같은_TC_가_두_번이면_400(env):
    db, project, tcs, a, _ = env
    with pytest.raises(HTTPException) as e:
        bulk_update_testcases(project.id, TestCaseBulkUpdate(items=[
            TestCaseBulkItem(id=tcs[0].id, expected_result="A", base_values={"expected_result": "원래"}),
            TestCaseBulkItem(id=tcs[0].id, expected_result="B", base_values={"expected_result": "원래"}),
        ]), db=db, current_user=a)
    assert e.value.status_code == 400
    assert _reload(db, tcs[0]).expected_result == "원래"


@pytest.mark.parametrize("bad", ["abc", [1], 5])
def test_커스텀_칸_기준값이_객체가_아니면_검증_오류(bad):
    with pytest.raises(ValidationError):
        TestCaseUpdate(custom_fields={"x": "1"}, base_values={"custom_fields": bad})
    with pytest.raises(ValidationError):
        TestCaseBulkItem(id=1, custom_fields={"x": "1"}, base_values={"custom_fields": bad})


def test_정수와_정수형_실수는_같은_값이다(env):
    """JSONB 에 2.0 으로 들어간 값을 브라우저는 2 로 읽어 기준값으로 보낸다. 다르게 보면 그 칸을 못 고친다."""
    db, _, tcs, a, _ = env
    tcs[0].custom_fields = {"x": 2.0}
    db.commit()
    resp = _put(env, a, tcs[0], custom_fields={"x": 3}, base_values={"custom_fields": {"x": 2}})
    assert not isinstance(resp, JSONResponse)
    assert _reload(db, tcs[0]).custom_fields == {"x": 3}


def test_큰_정수는_뭉개지_않고_비교한다(env):
    db, _, tcs, a, _ = env
    tcs[0].custom_fields = {"x": 9007199254740993}
    db.commit()
    body = _body(_put(env, a, tcs[0], custom_fields={"x": 0}, base_values={"custom_fields": {"x": 9007199254740992}}))
    assert body["conflicts"][0]["fields"] == ["custom_fields.x"]


def _wait_until_blocked(engine, timeout=10.0):
    """다른 세션이 잠금을 기다리기 시작할 때까지 본다. 고정 sleep 은 느린 러너에서 검출력을 잃는다."""
    s = sessionmaker(bind=engine)()
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            n = s.execute(text("SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
                               "WHERE NOT l.granted AND a.datname = current_database()")).scalar()
            s.rollback()
            if n:
                return
            time.sleep(0.05)
        raise AssertionError("잠금 대기가 생기지 않았다")
    finally:
        s.close()


def test_참과_1_은_다른_값이다(env):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], custom_fields={"x": True, "y": "y0"}, base_values={"custom_fields": {"x": "x0", "y": "y0"}})
    body = _body(_put(env, a, tcs[0], custom_fields={"x": 2, "y": "y0"}, base_values={"custom_fields": {"x": 1, "y": "y0"}}))
    assert body["conflicts"][0]["fields"] == ["custom_fields.x"]


def test_일괄_수정은_대상_행_전부를_id_순서로_먼저_잠근다(env, pg_engine):
    """기준값이 있는 행만 미리 잠그면 [id1 생략, id2 포함] 과 [id1 포함, id2 생략] 이 교착한다."""
    db, project, tcs, a, _ = env
    Session = sessionmaker(bind=pg_engine)
    holder = Session()
    holder.execute(text("SELECT id FROM test_cases WHERE id = :i FOR UPDATE"), {"i": tcs[0].id})
    done = []

    def bulk():
        s = Session()
        try:
            # 항목은 id 역순이다. 기준값 행만 잠그거나 항목 순서대로 잠그면 id2 를 먼저 쥔다
            bulk_update_testcases(project.id, TestCaseBulkUpdate(items=[
                TestCaseBulkItem(id=tcs[1].id, expected_result="포함", base_values={"expected_result": "원래"}),
                TestCaseBulkItem(id=tcs[0].id, remarks="생략"),
            ]), db=s, current_user=s.get(User, a.id))
            done.append(True)
        finally:
            s.close()

    th = threading.Thread(target=bulk)
    th.start()
    try:
        _wait_until_blocked(pg_engine)  # 앞 행(id1)에서 기다리는 중
        assert not done
        assert _row_free(pg_engine, tcs[1].id), "뒤 행을 먼저 쥐고 앞 행을 기다리면 교착한다"
    finally:
        holder.rollback()
        holder.close()
        th.join(timeout=10)
    assert done == [True]


def _row_free(engine, tc_id) -> bool:
    """다른 세션에서 그 행을 바로 잠글 수 있는지 본다."""
    probe = sessionmaker(bind=engine)()
    try:
        return probe.execute(text("SELECT id FROM test_cases WHERE id = :i FOR UPDATE NOWAIT"),
                             {"i": tc_id}).first() is not None
    finally:
        probe.rollback()
        probe.close()


def test_409_는_세션을_닫기_전에_행_잠금을_푼다(env, pg_engine):
    db, _, tcs, a, b = env
    _put(env, b, tcs[0], expected_result="B 값", base_values={"expected_result": "원래"})
    _body(_put(env, a, tcs[0], expected_result="A 값", base_values={"expected_result": "원래"}))
    # FastAPI 는 get_db 정리를 응답 뒤에 한다. 409 를 낸 세션이 잠금을 쥐고 있으면 다음 저장이 기다린다.
    assert _row_free(pg_engine, tcs[0].id)


def test_시트를_옮길_수_있는_요청은_프로젝트_잠금을_행_잠금보다_먼저_잡는다(pg_engine):
    s = sessionmaker(bind=pg_engine)()
    u = User(username="u", password_hash="x", display_name="U", role="admin")
    s.add(u)
    s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p)
    s.flush()
    s.add_all([TestCaseSheet(project_id=p.id, name="S", sort_order=0, is_folder=False),
               TestCaseSheet(project_id=p.id, name="T", sort_order=1, is_folder=False)])
    tc = TestCase(project_id=p.id, no=1, tc_id="T-1", expected_result="원래", sheet_name="S", created_by=u.id)
    s.add(tc)
    s.commit()
    pid, tid, uid = p.id, tc.id, u.id
    s.close()

    Session = sessionmaker(bind=pg_engine)
    holder = Session()
    # 정렬 · 삭제 · 시트 작업이 프로젝트 잠금을 쥐고 있는 상태
    holder.execute(text("SELECT pg_advisory_xact_lock(1, :p)"), {"p": pid})
    done = []

    def move():
        db = Session()
        try:
            update_testcase(pid, tid, TestCaseUpdate(sheet_name="T", base_values={"sheet_name": "S"}),
                            db=db, current_user=db.get(User, uid))
            done.append(True)
        finally:
            db.close()

    th = threading.Thread(target=move)
    th.start()
    try:
        _wait_until_blocked(pg_engine)  # 이동 요청이 프로젝트 잠금에서 기다리는 중
        assert not done
        # 기다리는 동안 행을 쥐고 있으면, 그 행을 고치려는 잠금 보유자와 교착한다
        assert _row_free(pg_engine, tid)
    finally:
        holder.rollback()
        holder.close()
        th.join(timeout=10)
    assert done == [True]
