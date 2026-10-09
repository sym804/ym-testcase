"""빈 DB 에 동시에 가입해도 관리자는 한 명이다.

라우트 함수를 독립 세션(독립 연결)으로 동시에 부른다. SQLite 에서는 쓰기 잠금이
줄을 세워 줬지만 PostgreSQL 의 READ COMMITTED 에서는 서로의 미커밋 행을 못 본다.
첫 계정 뒤로는 아이디 가입이 막히므로(이메일로 가입해 주세요) 한 명만 성공한다.
"""
import threading

from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from models import User, UserRole
from routes.auth import register
from schemas import UserCreate

N = 8


def _req(i):
    # ★IP 를 요청마다 다르게 준다. 같은 IP 면 가입 횟수 제한 잠금이 먼저 줄을 세워서
    #   계정 잠금을 빼도 이 테스트가 통과한다(QA2 지적, 잠금을 빼고 실패하는 것을 확인함).
    return Request({"type": "http", "method": "POST", "path": "/api/auth/register", "headers": [],
                    "client": (f"10.0.1.{i}", 0), "query_string": b""})


def test_빈_DB_에_동시에_가입해도_관리자는_한_명(pg_engine, monkeypatch):
    monkeypatch.setenv("REGISTER_MAX_PER_HOUR", "1000")
    Session = sessionmaker(bind=pg_engine)
    barrier = threading.Barrier(N)
    ok, rejected, errors = [], [], []

    def go(i):
        s = Session()
        try:
            barrier.wait()
            register(UserCreate(username=f"user{i}", password="Passw0rd!x", display_name=f"u{i}"), request=_req(i), db=s)
            ok.append(i)
        except HTTPException as e:
            rejected.append(e.status_code)
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
    assert len(ok) == 1 and rejected == [400] * (N - 1)
    assert roles == [UserRole.admin]
