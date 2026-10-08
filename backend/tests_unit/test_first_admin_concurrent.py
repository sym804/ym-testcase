"""빈 DB 에 동시에 가입해도 관리자는 한 명이다.

라우트 함수를 독립 세션(독립 연결)으로 동시에 부른다. SQLite 에서는 쓰기 잠금이
줄을 세워 줬지만 PostgreSQL 의 READ COMMITTED 에서는 서로의 미커밋 행을 못 본다.
"""
import threading

from sqlalchemy.orm import sessionmaker

from models import User, UserRole
from routes.auth import register
from schemas import UserCreate

N = 8


def test_빈_DB_에_동시에_가입해도_관리자는_한_명(pg_engine):
    Session = sessionmaker(bind=pg_engine)
    barrier = threading.Barrier(N)
    errors = []

    def go(i):
        s = Session()
        try:
            barrier.wait()
            register(UserCreate(username=f"user{i}", password="Passw0rd!x", display_name=f"u{i}"), db=s)
        except Exception as e:  # noqa: BLE001  실패도 결과로 모은다
            errors.append(repr(e))
        finally:
            s.close()

    threads = [threading.Thread(target=go, args=(i,)) for i in range(N)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    s = Session()
    roles = [u.role for u in s.query(User).all()]
    s.close()
    assert errors == []
    assert len(roles) == N
    assert roles.count(UserRole.admin) == 1, roles
