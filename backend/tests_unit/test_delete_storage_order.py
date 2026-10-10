"""삭제는 DB 커밋이 끝난 뒤에 저장소 객체를 지운다

예전에는 첨부 객체를 먼저 지우고 DB 를 커밋했다. 커밋이 실패하거나 시간 초과로 끊기면
프로젝트 · 수행 · 첨부 기록은 그대로 남는데 파일만 사라져, 화면에는 열리지 않는 첨부가
남았다. 지금은 지울 키를 커밋 전에 storage_deletions 에 적어 두고(같은 트랜잭션), 커밋한
뒤 저장소를 지우고 그 기록을 걷는다. 저장소가 실패하면 기록이 남아 일일 정리가 다시 지운다.

실행: cd backend && python -m pytest tests_unit/test_delete_storage_order.py -q
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy.orm import sessionmaker

from models import (
    Attachment, Project, StorageDeletion, TestCase, TestResult, TestResultValue, TestRun, User,
)
from routes import attachments
from routes.attachments import delete_attachment
from routes.projects import delete_project
from routes.testruns import delete_testrun


class _Storage:
    def __init__(self):
        self.objects = {"p/1.png": b"x"}
        self.fail = False

    def delete(self, keys):
        if self.fail:
            raise OSError("storage down")
        for k in keys:
            self.objects.pop(k, None)


class _CommitFails(Exception):
    pass


@pytest.fixture
def env(pg_engine, monkeypatch):
    st = _Storage()
    monkeypatch.setattr(attachments, "get_storage", lambda: st)
    Session = sessionmaker(bind=pg_engine)
    db = Session()
    user = User(username="a", password_hash="x", display_name="관리자", role="admin")
    db.add(user)
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.flush()
    tc = TestCase(project_id=project.id, no=1, tc_id="A-1", sheet_name="S", created_by=user.id)
    db.add(tc)
    run = TestRun(project_id=project.id, name="R", round=1, created_by=user.id)
    db.add(run)
    db.flush()
    res = TestResult(test_run_id=run.id, test_case_id=tc.id, result=TestResultValue.FAIL, executed_by=user.id)
    db.add(res)
    db.flush()
    att = Attachment(test_result_id=res.id, filename="1.png", filepath="p/1.png", uploaded_by=user.id)
    db.add(att)
    db.commit()
    ids = {"project": project.id, "run": run.id, "att": att.id}
    yield db, Session, st, user, ids
    db.close()


def _fail_commit(db, monkeypatch):
    def boom():
        raise _CommitFails("commit timeout")
    monkeypatch.setattr(db, "commit", boom)


def _call(kind, db, user, ids):
    if kind == "project":
        delete_project(ids["project"], db=db, current_user=user)
    elif kind == "run":
        delete_testrun(ids["project"], ids["run"], db=db, current_user=user)
    else:
        delete_attachment(ids["att"], db=db, current_user=user)


KINDS = ["project", "run", "attachment"]


@pytest.mark.parametrize("kind", KINDS)
def test_커밋이_실패하면_파일도_남는다(env, monkeypatch, kind):
    db, Session, st, user, ids = env
    _fail_commit(db, monkeypatch)
    with pytest.raises(_CommitFails):
        _call(kind, db, user, ids)
    assert "p/1.png" in st.objects, "DB 는 남았는데 파일만 지워졌다"
    db.rollback()
    s = Session()
    try:
        assert s.get(Attachment, ids["att"]) is not None
        assert s.query(StorageDeletion).count() == 0, "커밋이 안 됐으니 삭제 예약도 남지 않는다"
    finally:
        s.close()


@pytest.mark.parametrize("kind", KINDS)
def test_커밋_뒤_저장소를_지우고_예약을_걷는다(env, kind):
    db, Session, st, user, ids = env
    _call(kind, db, user, ids)
    assert st.objects == {}
    s = Session()
    try:
        assert s.get(Attachment, ids["att"]) is None
        assert s.query(StorageDeletion).count() == 0
    finally:
        s.close()


@pytest.mark.parametrize("kind", KINDS)
def test_저장소가_실패해도_삭제는_성공하고_다시_지울_기록이_남는다(env, kind):
    db, Session, st, user, ids = env
    st.fail = True
    _call(kind, db, user, ids)  # 예외 없이 끝난다(응답은 성공)
    assert "p/1.png" in st.objects
    s = Session()
    try:
        assert s.get(Attachment, ids["att"]) is None
        assert [k for (k,) in s.query(StorageDeletion.storage_key)] == ["p/1.png"]
    finally:
        s.close()
