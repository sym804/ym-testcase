"""리포트 파일명 날짜와 생성 시각은 서버 시간대와 무관하게 KST 다. Vercel 함수는 UTC 다."""
import datetime as dt
from types import SimpleNamespace

import routes.reports as reports


def test_UTC_시각을_KST_로_바꾼다():
    t = dt.datetime(2026, 10, 8, 16, 30, tzinfo=dt.timezone.utc)
    assert reports.report_now(t) == dt.datetime(2026, 10, 9, 1, 30)


def test_인자가_없으면_models_now_kst_와_같은_기준():
    a = reports.report_now()
    b = reports.now_kst()
    assert a.tzinfo is None
    assert abs((b - a).total_seconds()) < 5


def test_파일명_날짜는_report_now_에서_온다(monkeypatch):
    """호출부가 datetime.now() 로 돌아가면(서버 시간대 의존) 이 테스트가 깨진다."""
    monkeypatch.setattr(reports, "report_now", lambda now=None: dt.datetime(2031, 1, 2, 3, 4))
    run = SimpleNamespace(name="회귀", round=1, version=None, id=1)
    name = reports.report_filename("P", run, "pdf")
    assert "20310102" in name, name
