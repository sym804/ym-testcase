"""횟수 제한 기록. 요청 세션과 따로 자체 트랜잭션으로 쓴다.

★요청 세션으로 쓰면 그 요청이 예외(401, 429)로 끝날 때 기록도 같이 롤백된다.
  실패를 세는 것이 목적이라 실패 응답과 함께 사라지면 안 된다.
★시각은 DB 의 now() 를 쓴다. 실행 환경마다 시계가 조금씩 달라도 같은 기준으로 센다.
"""
from sqlalchemy import text


def _engine(engine):
    if engine is not None:
        return engine
    from database import engine as default
    return default


def count_recent(bucket: str, key: str, window_sec: int, engine=None) -> int:
    with _engine(engine).connect() as c:
        return c.execute(text(
            "SELECT count(*) FROM rate_limit_events WHERE bucket = :b AND key = :k "
            "AND created_at > now() - make_interval(secs => :w)"
        ), {"b": bucket, "k": key, "w": window_sec}).scalar()


def record(bucket: str, key: str, engine=None) -> None:
    with _engine(engine).begin() as c:
        c.execute(text("INSERT INTO rate_limit_events (bucket, key) VALUES (:b, :k)"),
                  {"b": bucket, "k": key})


def reserve(bucket: str, key: str, window_sec: int, limit: int, engine=None):
    """확인과 기록을 한 트랜잭션에서 한다. 상한 안이면 기록 id, 넘으면 None.

    ★검사 뒤에 기록하면 동시에 온 요청이 모두 같은 수를 보고 통과해 상한을 동시 요청 수만큼
      넘긴다. 이 키만 짧게 잠그고 바로 커밋하므로, 요청 트랜잭션이 bcrypt 동안 잠금을 쥐지 않는다.
    시도를 먼저 기록하고 성공하면 release 로 지운다. 결과적으로 실패만 남는다.
    """
    from fastapi import HTTPException
    from sqlalchemy.exc import OperationalError

    from services.locks import BUSY_DETAIL, LockNs, _LOCK_NOT_AVAILABLE, _wait_timeout_ms

    with _engine(engine).begin() as c:
        c.execute(text("SELECT set_config('lock_timeout', :v, true)"), {"v": f"{_wait_timeout_ms()}ms"})
        try:
            c.execute(text("SELECT pg_advisory_xact_lock(:ns, hashtext(:k))"),
                      {"ns": int(LockNs.RATE_LIMIT), "k": f"reserve:{bucket}:{key}"})
        except OperationalError as e:
            # 다른 요청 잠금과 같은 응답(locks._acquire). 500 으로 새지 않게 한다
            if getattr(e.orig, "pgcode", None) == _LOCK_NOT_AVAILABLE:
                raise HTTPException(status_code=409, detail=BUSY_DETAIL)
            raise
        n = c.execute(text(
            "SELECT count(*) FROM rate_limit_events WHERE bucket = :b AND key = :k "
            "AND created_at > now() - make_interval(secs => :w)"
        ), {"b": bucket, "k": key, "w": window_sec}).scalar()
        if n >= limit:
            return None
        return c.execute(text("INSERT INTO rate_limit_events (bucket, key) VALUES (:b, :k) RETURNING id"),
                         {"b": bucket, "k": key}).scalar()


def release(event_id: int, engine=None) -> None:
    """reserve 로 남긴 기록 하나를 지운다(성공한 시도)."""
    with _engine(engine).begin() as c:
        c.execute(text("DELETE FROM rate_limit_events WHERE id = :i"), {"i": event_id})


def clear(bucket: str, key: str, engine=None) -> None:
    with _engine(engine).begin() as c:
        c.execute(text("DELETE FROM rate_limit_events WHERE bucket = :b AND key = :k"),
                  {"b": bucket, "k": key})


def clear_all(engine=None) -> None:
    """테스트 격리용. 운영 코드에서 부르지 않는다."""
    with _engine(engine).begin() as c:
        c.execute(text("DELETE FROM rate_limit_events"))


def purge_older_than(seconds: int, engine=None) -> int:
    """오래된 기록을 지운다. Cron 정리 작업이 부른다."""
    with _engine(engine).begin() as c:
        return c.execute(text(
            "DELETE FROM rate_limit_events WHERE created_at < now() - make_interval(secs => :s)"
        ), {"s": seconds}).rowcount
