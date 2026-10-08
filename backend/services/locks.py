"""PostgreSQL advisory lock 으로 요청을 줄 세운다.

SQLite 는 쓰기를 파일 잠금으로 한 줄로 세워서, "최댓값을 읽고 +1 해서 쓰는" 코드가
우연히 안전했다. PostgreSQL 은 두 트랜잭션이 같은 값을 읽고 둘 다 쓴다.

★트랜잭션 잠금(xact)만 쓴다. 커밋이나 롤백에서 저절로 풀리므로 Supabase 트랜잭션
  풀러에서도 같은 트랜잭션 안에서는 유지된다. 세션 잠금은 풀러에서 다른 요청과 섞인다.
★중간 commit() 뒤에는 잠금이 풀린 새 트랜잭션이다. 번호를 다시 읽으면 다시 잡는다.
★무한정 기다리지 않는다. 기다리는 요청은 그동안 DB 연결을 쥐고 있어서, 긴 작업 하나가
  다른 프로젝트의 연결까지 말린다. 상한(LOCK_WAIT_TIMEOUT_MS)을 넘으면 409 로 다시
  시도하라고 알린다.
"""
import os
from enum import IntEnum

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from database import get_db

#: PostgreSQL lock_not_available. lock_timeout 을 넘기면 이 코드로 실패한다.
_LOCK_NOT_AVAILABLE = "55P03"
BUSY_DETAIL = "다른 작업이 진행 중입니다. 잠시 후 다시 시도해 주세요."


class LockNs(IntEnum):
    PROJECT_WRITE = 1
    FIRST_ADMIN = 2
    CRON = 3
    RATE_LIMIT = 4
    RUN_RESULTS = 5


def _wait_timeout_ms() -> int:
    return int(os.getenv("LOCK_WAIT_TIMEOUT_MS", "10000"))


def _acquire(db: Session, sql: str, params: dict) -> None:
    # set_config(..., true) 는 SET LOCAL 과 같다. 트랜잭션이 끝나면 저절로 돌아간다.
    db.execute(text("SELECT set_config('lock_timeout', :v, true)"), {"v": f"{_wait_timeout_ms()}ms"})
    try:
        db.execute(text(sql), params)
    except OperationalError as e:
        if getattr(e.orig, "pgcode", None) == _LOCK_NOT_AVAILABLE:
            raise HTTPException(status_code=409, detail=BUSY_DETAIL)
        raise
    # 뒤따르는 행 잠금(FOR UPDATE)에는 상한을 걸지 않는다(기본값으로 되돌림).
    db.execute(text("SELECT set_config('lock_timeout', '0', true)"))


def advisory_xact_lock(db: Session, ns: LockNs, key: int = 0) -> None:
    _acquire(db, "SELECT pg_advisory_xact_lock(:ns, :key)", {"ns": int(ns), "key": int(key)})


def keyed_xact_lock(db: Session, ns: LockNs, key: str) -> None:
    """문자열 키를 해시해 잠근다. 같은 키의 확인과 기록 사이를 줄 세운다."""
    _acquire(db, "SELECT pg_advisory_xact_lock(:ns, hashtext(:key))", {"ns": int(ns), "key": key})


def project_write_lock(project_id: int, db: Session = Depends(get_db)) -> None:
    """TC·시트를 바꾸는 요청을 프로젝트별로 줄 세운다.

    번호(no), TC ID, 시트 순서, 다음 회차가 모두 "현재 값을 읽고 정하는" 구조라
    라우트마다 따로 잠그면 빠뜨린다. 프로젝트 단위로 한 번에 잡는다.
    셀 하나를 고치는 수정(시트 이동 없음)과 파일 파싱처럼 번호와 무관한 구간은 잠그지
    않는다. 그런 라우트는 의존성 대신 본문에서 advisory_xact_lock 을 직접 부른다.
    """
    advisory_xact_lock(db, LockNs.PROJECT_WRITE, project_id)
