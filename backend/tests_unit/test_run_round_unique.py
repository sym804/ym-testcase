"""같은 프로젝트, 같은 이름의 수행은 회차가 겹치지 않는다.

다음 회차는 max(round)+1 이다. 프로젝트 잠금이 요청을 줄 세우지만 DB 도 막는다.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from models import Project, TestRun, User


def _project(s):
    u = User(username="u", password_hash="x", display_name="u")
    s.add(u)
    s.flush()
    p = Project(name="P", created_by=u.id)
    s.add(p)
    s.flush()
    return u, p


def test_같은_이름_같은_회차는_거부된다(pg_session):
    u, p = _project(pg_session)
    pg_session.add(TestRun(project_id=p.id, name="R", round=1, created_by=u.id))
    pg_session.flush()
    pg_session.add(TestRun(project_id=p.id, name="R", round=1, created_by=u.id))
    with pytest.raises(IntegrityError):
        pg_session.flush()


def test_이름이_다르면_같은_회차도_된다(pg_session):
    u, p = _project(pg_session)
    pg_session.add(TestRun(project_id=p.id, name="R", round=1, created_by=u.id))
    pg_session.add(TestRun(project_id=p.id, name="Q", round=1, created_by=u.id))
    pg_session.flush()
