"""테스트 소스에 SQLite 엔진이 남아 있으면 실패한다.

SQLite 엔진을 직접 만드는 테스트는 DATABASE_URL 과 무관하게 SQLite 에서 돌아,
PostgreSQL 에서 깨지는 코드를 통과시킨다(전환 전 27개 파일이 그랬다).
"""
import os
import re

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERN = re.compile(r"sqlite(\+\w+)?://|import sqlite3")
#: SQLite 주소를 거부하는지 확인하는 테스트는 문자열로 SQLite 주소를 쓴다.
ALLOWED = {
    os.path.join("tests_unit", "test_no_sqlite_in_tests.py"),
    os.path.join("tests_unit", "test_db_config.py"),
}


def test_테스트에_sqlite_가_없다():
    hits = []
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".pytest_cache", "venv", ".venv"}]
        for f in files:
            if not (f.startswith("test_") and f.endswith(".py")) and f != "conftest.py":
                continue
            rel = os.path.relpath(os.path.join(root, f), BACKEND)
            if rel in ALLOWED:
                continue
            with open(os.path.join(root, f), encoding="utf-8") as fh:
                for i, line in enumerate(fh, 1):
                    if PATTERN.search(line):
                        hits.append(f"{rel}:{i}: {line.strip()}")
    assert hits == [], "\n".join(hits)
