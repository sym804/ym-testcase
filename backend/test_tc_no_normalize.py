"""시트 안의 no 를 1 부터 이어지게 되돌리는 마이그레이션.

복제가 프로젝트 전체 max(no)+1 을 주던 동안 시트 안 번호에 구멍이 생겼다.
실측에서 23개 시트 중 13개가 max(no) 와 TC 수가 어긋나 있었다.

살아 있는 TC 를 1..N 으로 다시 매기고, 지운 TC 는 그 뒤로 민다. 지운 것을
그 자리에 두면 되살릴 때 살아 있는 TC 와 번호가 겹친다.

실행: cd backend && TEST_PORT=8009 TEST_BASE_URL=http://127.0.0.1:8009 python -m pytest test_tc_no_normalize.py -v
"""
import importlib.util
import os
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MIGRATION = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "alembic", "versions", "f2b7c04e91a8_normalize_testcase_no_per_sheet.py",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("_norm_mig", MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def db(tmp_path):
    """마이그레이션이 손대는 컬럼만 가진 최소 테이블."""
    url = f"sqlite:///{(tmp_path / 'norm.db').as_posix()}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE test_cases ("
            " id INTEGER PRIMARY KEY AUTOINCREMENT,"
            " project_id INTEGER NOT NULL,"
            " sheet_name VARCHAR(100) NOT NULL DEFAULT '기본',"
            " no INTEGER NOT NULL,"
            " deleted_at DATETIME)"
        ))
    s = sessionmaker(bind=engine)()
    yield s, engine
    s.close()
    engine.dispose()


def _add(session, project_id, sheet, no, deleted=False):
    session.execute(text(
        "INSERT INTO test_cases (project_id, sheet_name, no, deleted_at) "
        "VALUES (:p, :s, :n, :d)"
    ), {"p": project_id, "s": sheet, "n": no, "d": "2026-01-01" if deleted else None})


def _rows(session, project_id, sheet, alive=True):
    cond = "IS NULL" if alive else "IS NOT NULL"
    return [
        (r[0], r[1]) for r in session.execute(text(
            f"SELECT id, no FROM test_cases WHERE project_id=:p AND sheet_name=:s "
            f"AND deleted_at {cond} ORDER BY no"
        ), {"p": project_id, "s": sheet})
    ]


def _run(session):
    _load_migration().normalize(session.connection())
    session.commit()


def test_fills_gaps_within_sheet(db):
    """구멍이 난 번호를 1 부터 이어 붙인다. 순서는 그대로다."""
    s, _ = db
    _add(s, 1, "결제", 4)
    _add(s, 1, "결제", 5)
    _add(s, 1, "결제", 51)

    _run(s)

    assert [no for _, no in _rows(s, 1, "결제")] == [1, 2, 3]


def test_keeps_existing_order(db):
    """번호만 바꾸고 순서는 바꾸지 않는다."""
    s, _ = db
    _add(s, 1, "결제", 51)   # id 1
    _add(s, 1, "결제", 4)    # id 2
    _add(s, 1, "결제", 5)    # id 3

    _run(s)

    assert _rows(s, 1, "결제") == [(2, 1), (3, 2), (1, 3)]


def test_each_sheet_starts_at_one(db):
    """시트마다 따로 센다."""
    s, _ = db
    _add(s, 1, "로그인", 10)
    _add(s, 1, "로그인", 20)
    _add(s, 1, "결제", 30)

    _run(s)

    assert [no for _, no in _rows(s, 1, "로그인")] == [1, 2]
    assert [no for _, no in _rows(s, 1, "결제")] == [1]


def test_projects_do_not_mix(db):
    """프로젝트가 다르면 같은 시트 이름이어도 따로 센다."""
    s, _ = db
    _add(s, 1, "결제", 7)
    _add(s, 2, "결제", 9)

    _run(s)

    assert [no for _, no in _rows(s, 1, "결제")] == [1]
    assert [no for _, no in _rows(s, 2, "결제")] == [1]


def test_deleted_moves_behind_alive(db):
    """지운 TC 는 살아 있는 번호 뒤로 민다. 되살릴 때 겹치면 안 된다."""
    s, _ = db
    _add(s, 1, "결제", 1)
    _add(s, 1, "결제", 2, deleted=True)
    _add(s, 1, "결제", 3)

    _run(s)

    alive = [no for _, no in _rows(s, 1, "결제")]
    dead = [no for _, no in _rows(s, 1, "결제", alive=False)]
    assert alive == [1, 2]
    assert dead == [3], "지운 것이 살아 있는 번호와 겹치면 복원할 때 중복이 된다"


def test_large_sheet_is_ranked_once(db):
    """행이 많아도 순위를 한 번만 매긴다.

    갱신 대상과 같은 테이블을 읽는 순위 계산은, 행마다 다시 평가되면 이미 바꾼 값
    위에서 순위를 매겨 결과가 뭉개진다. 3행짜리로는 실행 계획이 달라 안 걸린다.
    """
    s, _ = db
    n = 500
    for i in range(n):
        # 번호를 거꾸로 넣는다. 순위를 다시 매기면 순서가 뒤집힌 채로 굳는다.
        _add(s, 1, "결제", (n - i) * 3)

    _run(s)

    rows = _rows(s, 1, "결제")
    assert [no for _, no in rows] == list(range(1, n + 1))
    # 넣은 번호가 클수록 나중이므로, id 는 역순이어야 한다.
    assert [i for i, _ in rows] == list(range(n, 0, -1))


def test_is_idempotent(db):
    """두 번 돌려도 결과가 같다."""
    s, _ = db
    _add(s, 1, "결제", 4)
    _add(s, 1, "결제", 9)

    _run(s)
    first = _rows(s, 1, "결제")
    _run(s)

    assert _rows(s, 1, "결제") == first
