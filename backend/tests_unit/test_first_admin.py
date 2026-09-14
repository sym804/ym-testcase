"""최초 관리자는 한 명이다

`User.count() == 0` 을 보고 관리자를 주는데, 같은 순간에 두 가입 요청이 들어오면
둘 다 0 을 보고 둘 다 관리자가 된다. 최초 관리자 한 명이라는 전제가 깨진다.

삽입한 뒤 자기보다 먼저 만들어진 사용자가 있는지 다시 본다. 있으면 경쟁에서 진
쪽이므로 일반 사용자로 돌린다. 판정이 삽입 뒤로 가서 창이 닫힌다.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base, User, UserRole
from services.first_admin import demote_if_not_first


@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'admin.db'}".replace("\\", "/")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _add(db, username: str, role: UserRole) -> User:
    user = User(username=username, password_hash="x", display_name=username, role=role)
    db.add(user)
    db.flush()
    return user


def test_혼자면_관리자로_남는다(db):
    user = _add(db, "first", UserRole.admin)

    demote_if_not_first(db, user)

    assert user.role == UserRole.admin


def test_먼저_만들어진_사용자가_있으면_강등한다(db):
    _add(db, "winner", UserRole.admin)
    loser = _add(db, "loser", UserRole.admin)

    demote_if_not_first(db, loser)

    assert loser.role == UserRole.user, "경쟁에서 진 쪽이 관리자로 남았다"


def test_일반_사용자는_건드리지_않는다(db):
    _add(db, "admin", UserRole.admin)
    normal = _add(db, "normal", UserRole.user)

    demote_if_not_first(db, normal)

    assert normal.role == UserRole.user


def test_이미_관리자가_있는_상태의_두_번째_관리자는_그대로_둔다(db):
    """사람이 손으로 올려 준 관리자까지 끌어내리면 안 된다."""
    first = _add(db, "first", UserRole.admin)
    promoted = _add(db, "promoted", UserRole.user)
    db.commit()

    # 관리자로 승격시킨 뒤에는 이 함수를 부르지 않는다. 불러도 가입 직후가
    # 아니므로 대상이 아니다.
    promoted.role = UserRole.admin
    db.commit()

    assert first.role == UserRole.admin
    assert promoted.role == UserRole.admin
