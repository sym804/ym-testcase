"""리포트 파일명 날짜와 생성 시각은 서버 시간대와 무관하게 KST 다. Vercel 함수는 UTC 다."""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

CODE = (
    "import datetime, routes.reports as r;"
    "t = datetime.datetime(2026, 10, 8, 16, 30, tzinfo=datetime.timezone.utc);"
    "print(r.report_now(t).strftime('%Y%m%d %H'));"
    "print(r.report_now().tzinfo)"
)


def test_UTC_서버에서도_KST_날짜():
    env = dict(os.environ, TZ="UTC", DATABASE_URL="postgresql+psycopg2://u:p@127.0.0.1:1/x")
    r = subprocess.run([sys.executable, "-c", CODE], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    day, tz = r.stdout.split("\n")[:2]
    assert day == "20261009 01"
    assert tz == "None", "DB 값(KST naive)과 같은 형태로 낸다"
