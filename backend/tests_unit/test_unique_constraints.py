"""중복을 DB 가 막는다

조회한 뒤 삽입하는 방식만으로는 동시에 들어온 두 요청을 막지 못한다.
멤버가 둘이면 `.first()` 가 아무 역할이나 돌려주어 권한 판정이 비결정적이 되고,
같은 이름의 시트가 둘이면 rename/delete 가 한쪽만 건드려 데이터가 갈라진다.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from models import Base, Project, ProjectMember, TestCaseSheet, User


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'uniq.db'}".replace("\\", "/")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def seed(db):
    user = User(username="u", password_hash="x", display_name="U", role="admin")
    other = User(username="v", password_hash="x", display_name="V", role="user")
    db.add_all([user, other])
    db.flush()
    project = Project(name="P", created_by=user.id)
    db.add(project)
    db.commit()
    return project, user, other


def test_같은_사용자를_한_프로젝트에_두_번_넣을_수_없다(db, seed):
    project, _, other = seed
    db.add(ProjectMember(project_id=project.id, user_id=other.id, role="tester"))
    db.commit()

    db.add(ProjectMember(project_id=project.id, user_id=other.id, role="admin"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_다른_프로젝트에는_같은_사용자를_넣을_수_있다(db, seed):
    project, user, other = seed
    second = Project(name="P2", created_by=user.id)
    db.add(second)
    db.flush()

    db.add(ProjectMember(project_id=project.id, user_id=other.id, role="tester"))
    db.add(ProjectMember(project_id=second.id, user_id=other.id, role="tester"))
    db.commit()

    assert db.query(ProjectMember).count() == 2


def test_같은_이름의_시트를_한_프로젝트에_두_번_만들_수_없다(db, seed):
    project, _, _ = seed
    db.add(TestCaseSheet(project_id=project.id, name="결제", sort_order=0, is_folder=False))
    db.commit()

    db.add(TestCaseSheet(project_id=project.id, name="결제", sort_order=1, is_folder=False))
    with pytest.raises(IntegrityError):
        db.commit()


def test_다른_프로젝트에는_같은_시트_이름을_쓸_수_있다(db, seed):
    project, user, _ = seed
    second = Project(name="P2", created_by=user.id)
    db.add(second)
    db.flush()

    db.add(TestCaseSheet(project_id=project.id, name="결제", sort_order=0, is_folder=False))
    db.add(TestCaseSheet(project_id=second.id, name="결제", sort_order=0, is_folder=False))
    db.commit()

    assert db.query(TestCaseSheet).count() == 2
