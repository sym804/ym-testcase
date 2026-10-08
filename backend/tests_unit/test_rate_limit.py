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
