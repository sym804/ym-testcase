"""PostgreSQL advisory lock 으로 요청을 줄 세운다.

SQLite 는 쓰기를 파일 잠금으로 한 줄로 세워서, "최댓값을 읽고 +1 해서 쓰는" 코드가
우연히 안전했다. PostgreSQL 은 두 트랜잭션이 같은 값을 읽고 둘 다 쓴다.

★트랜잭션 잠금(xact)만 쓴다. 커밋이나 롤백에서 저절로 풀리므로 Supabase 트랜잭션
  풀러에서도 같은 트랜잭션 안에서는 유지된다. 세션 잠금은 풀러에서 다른 요청과 섞인다.
★중간 commit() 뒤에는 잠금이 풀린 새 트랜잭션이다. 번호를 다시 읽으면 다시 잡는다.
"""
from enum import IntEnum

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from database import get_db


class LockNs(IntEnum):
    PROJECT_WRITE = 1
    FIRST_ADMIN = 2
    CRON = 3


def advisory_xact_lock(db: Session, ns: LockNs, key: int = 0) -> None:
    db.execute(text("SELECT pg_advisory_xact_lock(:ns, :key)"), {"ns": int(ns), "key": int(key)})


def project_write_lock(project_id: int, db: Session = Depends(get_db)) -> None:
    """TC·시트를 바꾸는 요청을 프로젝트별로 줄 세운다.

    번호(no), TC ID, 시트 순서, 다음 회차가 모두 "현재 값을 읽고 정하는" 구조라
    라우트마다 따로 잠그면 빠뜨린다. 프로젝트 단위로 한 번에 잡는다.
    """
    advisory_xact_lock(db, LockNs.PROJECT_WRITE, project_id)
