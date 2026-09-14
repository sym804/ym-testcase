"""유니크 제약 마이그레이션이 데이터를 지나치게 지우지 않는다

`b7c31d9e42f8` 은 유니크 인덱스를 걸기 전에 중복을 정리한다. 그런데
`test_case_sheets.parent_id` 가 `ON DELETE CASCADE` 라, 중복 이름의 시트를
지우면 그것을 부모로 둔 하위 시트가 통째로 연쇄 삭제된다. 중복을 정리하려다
멀쩡한 하위 트리를 잃는다.

지우기 전에 하위 시트를 남는 쪽으로 옮긴다. TC 는 `sheet_name` 문자열로 이어져
있어서 시트 행이 하나로 합쳐져도 그대로 붙는다.

이 프로젝트의 실 DB 에는 중복도 하위 시트도 없어서 이 경로를 타지 않는다.
공개 레포라 다른 설치본에서 물린다.
"""
import os
import subprocess
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import sqlite3

PREV_REVISION = "a3d61f0c8be2"
TARGET_REVISION = "b7c31d9e42f8"


def _alembic(db_path: str, *args: str):
    env = dict(os.environ)
    env["DATABASE_URL"] = f"sqlite:///{db_path.replace(os.sep, '/')}"
    proc = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, f"alembic {args} 실패:\n{proc.stdout}\n{proc.stderr}"
    return proc


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "dedup.db")


def _seed_duplicates(db_path: str):
    """중복 시트 두 벌과 그 아래 하위 시트, 중복 멤버를 넣는다."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (id, username, password_hash, display_name, role, must_change_password)"
        " VALUES (1, 'u', 'x', 'U', 'admin', 0)"
    )
    cur.execute(
        "INSERT INTO projects (id, name, created_by, is_private) VALUES (1, 'P', 1, 0)"
    )

    # 같은 이름의 폴더 둘. 뒤엣것(id 20)이 정리 대상이다.
    cur.execute(
        "INSERT INTO test_case_sheets (id, project_id, name, sort_order, parent_id, is_folder)"
        " VALUES (10, 1, '묶음', 0, NULL, 1)"
    )
    cur.execute(
        "INSERT INTO test_case_sheets (id, project_id, name, sort_order, parent_id, is_folder)"
        " VALUES (20, 1, '묶음', 1, NULL, 1)"
    )
    # 지워질 쪽(20)을 부모로 둔 하위 시트
    cur.execute(
        "INSERT INTO test_case_sheets (id, project_id, name, sort_order, parent_id, is_folder)"
        " VALUES (30, 1, '결제', 0, 20, 0)"
    )
    # 중복 멤버
    cur.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (1, 1, 1, 'tester')"
    )
    cur.execute(
        "INSERT INTO project_members (id, project_id, user_id, role) VALUES (2, 1, 1, 'admin')"
    )
    conn.commit()
    conn.close()


def test_중복_정리가_하위_시트를_연쇄_삭제하지_않는다(db_path):
    _alembic(db_path, "upgrade", PREV_REVISION)
    _seed_duplicates(db_path)

    _alembic(db_path, "upgrade", TARGET_REVISION)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, name, parent_id FROM test_case_sheets ORDER BY id"
    ).fetchall()
    conn.close()

    ids = {r[0] for r in rows}
    assert 30 in ids, f"하위 시트가 연쇄 삭제됐다: {rows}"
    assert 10 in ids, f"남겨야 할 시트가 없다: {rows}"
    assert 20 not in ids, f"중복이 정리되지 않았다: {rows}"

    child = next(r for r in rows if r[0] == 30)
    assert child[2] == 10, f"하위 시트가 남은 부모로 옮겨지지 않았다: {child}"


def test_중복_멤버는_가장_오래된_하나만_남는다(db_path):
    _alembic(db_path, "upgrade", PREV_REVISION)
    _seed_duplicates(db_path)

    _alembic(db_path, "upgrade", TARGET_REVISION)

    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT id, role FROM project_members").fetchall()
    conn.close()

    assert len(rows) == 1, f"중복 멤버가 남았다: {rows}"
    assert rows[0][0] == 1, f"가장 오래된 행이 아니라 다른 행이 남았다: {rows}"


def test_유니크_인덱스가_실제로_걸린다(db_path):
    _alembic(db_path, "upgrade", TARGET_REVISION)

    conn = sqlite3.connect(db_path)
    member_idx = conn.execute(
        "SELECT [unique] FROM pragma_index_list('project_members')"
        " WHERE name = 'ix_project_members_project_user'"
    ).fetchone()
    sheet_idx = conn.execute(
        "SELECT [unique] FROM pragma_index_list('test_case_sheets')"
        " WHERE name = 'uq_test_case_sheets_project_name'"
    ).fetchone()
    conn.close()

    assert member_idx and member_idx[0] == 1
    assert sheet_idx and sheet_idx[0] == 1


def _seed_folder_and_sheet(db_path: str):
    """같은 이름의 폴더(먼저 만듦)와 일반 시트(나중), 그리고 그 시트의 TC."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO users (id, username, password_hash, display_name, role, must_change_password)"
        " VALUES (1, 'u', 'x', 'U', 'admin', 0)"
    )
    cur.execute(
        "INSERT INTO projects (id, name, created_by, is_private) VALUES (1, 'P', 1, 0)"
    )
    # id 가 작은 쪽이 폴더다. MIN(id) 로 남기면 폴더가 살아남는다.
    cur.execute(
        "INSERT INTO test_case_sheets (id, project_id, name, sort_order, parent_id, is_folder)"
        " VALUES (10, 1, '결제', 0, NULL, 1)"
    )
    cur.execute(
        "INSERT INTO test_case_sheets (id, project_id, name, sort_order, parent_id, is_folder)"
        " VALUES (20, 1, '결제', 1, NULL, 0)"
    )
    cur.execute(
        "INSERT INTO test_cases (id, project_id, no, tc_id, sheet_name, test_steps,"
        " expected_result, created_by) VALUES (1, 1, 1, 'TC-001', '결제', '1. 실행', '성공', 1)"
    )
    conn.commit()
    conn.close()


def test_폴더와_일반_시트가_겹치면_일반_시트를_남긴다(db_path):
    """★TC 는 sheet_name 문자열로 이어진다. 폴더만 남으면 그 TC 가 폴더 소속이 되어
    시트 순서에서 빠지고 수행 범위로도 고를 수 없게 된다. 담을 방법이 없는 TC 다."""
    _alembic(db_path, "upgrade", PREV_REVISION)
    _seed_folder_and_sheet(db_path)

    _alembic(db_path, "upgrade", TARGET_REVISION)

    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT id, is_folder FROM test_case_sheets WHERE name = '결제'"
    ).fetchall()
    tc_sheet = conn.execute("SELECT sheet_name FROM test_cases WHERE id = 1").fetchone()
    conn.close()

    assert len(rows) == 1, f"중복이 정리되지 않았다: {rows}"
    assert rows[0][1] == 0, f"폴더가 남아 TC 가 폴더 소속이 됐다: {rows}"
    assert tc_sheet[0] == "결제", "TC 가 사라졌다"
