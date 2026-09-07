"""b7d3c9a1e450 마이그레이션 검증

이 마이그레이션은 앱 기동 시 자동 실행되므로(`main.py` lifespan), 중복이 있는 DB 에서
실패하면 앱이 아예 뜨지 않는다. 다른 PC 의 설치본이 그 상황일 수 있어서
"중복을 먼저 정리하고 인덱스를 건다"가 지켜지는지 확인한다.
"""
import importlib.util
import os
import sys

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

MIGRATION = os.path.join(
    BACKEND, "alembic", "versions", "b7d3c9a1e450_unique_tc_id_per_project.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("mig_b7d3c9a1e450", MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mig = _load_migration()


# ── _free (빈 번호 찾기) ──────────────────────────────────────────────────────
# services/tc_id_service.allocate_tc_id 를 마이그레이션 안에 옮겨 둔 사본이다.
# 규칙이 갈라지면 정리 결과와 런타임 채번이 어긋나므로 같이 확인한다.

def test_free_규칙이_서비스와_같다():
    from services.tc_id_service import allocate_tc_id

    for base, taken in [
        ("A-001", {"A-001"}),
        ("A-001", {"A-001", "A-001-2"}),
        ("B-9", set()),
        ("", set()),
        ("X" * 60, {("X" * 60)[:50]}),
    ]:
        assert mig._free(base, set(taken)) == allocate_tc_id(base, set(taken)), base


# ── _dedupe ───────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE test_cases (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    no INTEGER NOT NULL,
    tc_id VARCHAR(50) NOT NULL,
    deleted_at DATETIME
);
"""


@pytest.fixture
def bind(tmp_path):
    engine = create_engine(f"sqlite:///{str(tmp_path / 'm.db')}")
    with engine.begin() as conn:
        conn.execute(sa.text(SCHEMA))
    with engine.begin() as conn:
        yield conn


def _insert(conn, rows):
    for i, (pid, no, tc_id, deleted) in enumerate(rows, start=1):
        conn.execute(
            sa.text(
                "INSERT INTO test_cases (id, project_id, no, tc_id, deleted_at) "
                "VALUES (:i, :p, :n, :t, :d)"
            ),
            {"i": i, "p": pid, "n": no, "t": tc_id, "d": deleted},
        )


def _rows(conn, project_id=None):
    q = "SELECT id, tc_id FROM test_cases WHERE deleted_at IS NULL"
    params = {}
    if project_id is not None:
        q += " AND project_id = :p"
        params["p"] = project_id
    return {r[0]: r[1] for r in conn.execute(sa.text(q), params)}


def test_중복이_없으면_아무것도_안_바꾼다(bind):
    _insert(bind, [(1, 1, "A-001", None), (1, 2, "A-002", None)])
    before = _rows(bind)
    assert mig._dedupe(bind) == 0
    assert _rows(bind) == before


def test_가장_먼저_만든_행이_원래_ID_를_지킨다(bind):
    _insert(bind, [(1, 1, "A-001", None), (1, 2, "A-001", None), (1, 3, "A-001", None)])
    assert mig._dedupe(bind) == 2
    got = _rows(bind)
    assert got[1] == "A-001"
    assert sorted(got.values()) == ["A-001", "A-001-2", "A-001-3"]


def test_이미_쓰이는_번호를_비켜_간다(bind):
    """A-001 이 셋, A-001-2 가 이미 따로 있으면 -3, -4 로 가야 한다."""
    _insert(bind, [
        (1, 1, "A-001", None), (1, 2, "A-001", None), (1, 3, "A-001", None),
        (1, 4, "A-001-2", None),
    ])
    assert mig._dedupe(bind) == 2
    got = _rows(bind)
    assert sorted(got.values()) == ["A-001", "A-001-2", "A-001-3", "A-001-4"]


def test_프로젝트끼리는_안_섞인다(bind):
    _insert(bind, [(1, 1, "A-001", None), (2, 1, "A-001", None)])
    assert mig._dedupe(bind) == 0
    assert sorted(_rows(bind).values()) == ["A-001", "A-001"]


def test_소프트_삭제된_행은_건드리지_않는다(bind):
    _insert(bind, [
        (1, 1, "A-001", None),
        (1, 2, "A-001", "2026-01-01 00:00:00"),
        (1, 3, "A-001", None),
    ])
    assert mig._dedupe(bind) == 1
    survivors = _rows(bind)
    assert sorted(survivors.values()) == ["A-001", "A-001-2"]
    deleted = bind.execute(
        sa.text("SELECT tc_id FROM test_cases WHERE deleted_at IS NOT NULL")
    ).fetchone()
    assert deleted[0] == "A-001"  # 삭제된 행은 원래 ID 유지


def test_정리_후_유니크_인덱스가_걸린다(bind):
    """중복이 있는 DB 에서도 인덱스 생성이 실패하지 않아야 한다."""
    _insert(bind, [(1, 1, "A-001", None), (1, 2, "A-001", None), (1, 3, "", None)])
    mig._dedupe(bind)
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX uq_test_cases_project_tc_id "
        "ON test_cases (project_id, tc_id) WHERE deleted_at IS NULL"
    ))
    # 인덱스가 실제로 중복을 막는지
    with pytest.raises(sa.exc.IntegrityError):
        bind.execute(sa.text(
            "INSERT INTO test_cases (id, project_id, no, tc_id, deleted_at) "
            "VALUES (99, 1, 9, 'A-001', NULL)"
        ))


def test_삭제된_행과는_겹쳐도_된다(bind):
    """부분 인덱스라 지운 TC 의 ID 를 다시 쓸 수 있어야 한다."""
    _insert(bind, [(1, 1, "A-001", "2026-01-01 00:00:00")])
    bind.execute(sa.text(
        "CREATE UNIQUE INDEX uq_test_cases_project_tc_id "
        "ON test_cases (project_id, tc_id) WHERE deleted_at IS NULL"
    ))
    bind.execute(sa.text(
        "INSERT INTO test_cases (id, project_id, no, tc_id, deleted_at) "
        "VALUES (2, 1, 2, 'A-001', NULL)"
    ))
    assert sorted(_rows(bind).values()) == ["A-001"]
