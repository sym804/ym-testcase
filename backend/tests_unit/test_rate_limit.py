"""실패 횟수는 DB 에 쌓여 여러 실행 환경(서버리스 인스턴스)이 같은 값을 본다."""
from sqlalchemy import create_engine, text

from services import rate_limit


def test_기록하면_다른_엔진에서도_보인다(pg_engine):
    other = create_engine(pg_engine.url, connect_args={"options": f"-csearch_path={pg_engine._ymtc_schema}"})
    try:
        rate_limit.record("login", "1.2.3.4:u", engine=pg_engine)
        rate_limit.record("login", "1.2.3.4:u", engine=pg_engine)
        assert rate_limit.count_recent("login", "1.2.3.4:u", 300, engine=other) == 2
    finally:
        other.dispose()


def test_창_밖의_기록은_세지_않는다(pg_engine):
    rate_limit.record("login", "k", engine=pg_engine)
    with pg_engine.begin() as c:
        c.execute(text("UPDATE rate_limit_events SET created_at = now() - interval '10 minutes'"))
    assert rate_limit.count_recent("login", "k", 300, engine=pg_engine) == 0


def test_버킷이_다르면_따로_센다(pg_engine):
    rate_limit.record("login", "k", engine=pg_engine)
    assert rate_limit.count_recent("account_submit", "k", 300, engine=pg_engine) == 0


def test_clear_는_그_키만_지운다(pg_engine):
    rate_limit.record("login", "a", engine=pg_engine)
    rate_limit.record("login", "b", engine=pg_engine)
    rate_limit.clear("login", "a", engine=pg_engine)
    assert rate_limit.count_recent("login", "a", 300, engine=pg_engine) == 0
    assert rate_limit.count_recent("login", "b", 300, engine=pg_engine) == 1


def test_오래된_행을_지운다(pg_engine):
    rate_limit.record("account_submit", "x", engine=pg_engine)
    with pg_engine.begin() as c:
        c.execute(text("UPDATE rate_limit_events SET created_at = now() - interval '2 hours'"))
    rate_limit.record("account_submit", "y", engine=pg_engine)
    assert rate_limit.purge_older_than(3600, engine=pg_engine) == 1
    assert rate_limit.count_recent("account_submit", "y", 300, engine=pg_engine) == 1


def test_로그인_제한은_요청_세션의_DB_를_본다(pg_engine, pg_session):
    """기본 엔진이 아니라 요청 세션이 붙은 DB 에서 센다. 테스트가 get_db 를 바꿔도,
    서버리스에서 연결이 달라도 같은 DB 를 본다(QA2: 기본 엔진은 개발 DB 를 가리킬 수 있다)."""
    import pytest
    from fastapi import HTTPException
    from starlette.requests import Request

    from routes.auth import LOGIN_MAX_FAILURES, _check_rate_limit, _rate_limit_key

    req = Request({"type": "http", "headers": [], "client": ("10.9.9.9", 1)})
    for _ in range(LOGIN_MAX_FAILURES):
        rate_limit.record("login", _rate_limit_key(req, "u"), engine=pg_engine)
    with pytest.raises(HTTPException) as e:
        _check_rate_limit(req, "u", pg_session)
    assert e.value.status_code == 429
