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
