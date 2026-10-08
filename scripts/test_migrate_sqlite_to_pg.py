"""SQLite(legacy) -> PostgreSQL 이관 스크립트.

원본은 legacy_schema.json(실 DB 의 칸 구성, 데이터 없음)으로 만든 임시 SQLite, 대상은 로컬
PostgreSQL 의 임시 DB(alembic head)다. 실 DB 와 uploads 는 쓰지 않는다.

실행: python -m pytest -q scripts/test_migrate_sqlite_to_pg.py
"""
import json
import os
import sqlite3
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), "backend")
sys.path.insert(0, HERE)
sys.path.insert(0, BACKEND)

import testing_db  # noqa: E402

LEGACY_HEAD = "5e0b8c2d4f17"
SCHEMA = json.load(open(os.path.join(HERE, "legacy_schema.json"), encoding="utf-8"))
TS = "2026-03-16 11:18:16.489532"


# ── 원본 SQLite ──────────────────────────────────────────────────────────────

def _create_legacy(path, schema=SCHEMA):
    con = sqlite3.connect(path)
    for table, spec in schema.items():
        cols = []
        pks = [c[0] for c in spec["columns"] if c[3]]
        for name, typ, notnull, _pk in spec["columns"]:
            cols.append(f'"{name}" {typ}' + (" NOT NULL" if notnull else ""))
        if pks:
            cols.append("PRIMARY KEY (" + ", ".join(f'"{p}"' for p in pks) + ")")
        for col, ref, refcol in spec["foreign_keys"]:
            cols.append(f'FOREIGN KEY ("{col}") REFERENCES "{ref}" ("{refcol}")')
        con.execute(f'CREATE TABLE "{table}" ({", ".join(cols)})')
    con.commit()
    return con


def base_rows():
    """화면에 나오는 핵심 흐름이 다 들어간 최소 데이터."""
    return {
        "alembic_version": [{"version_num": LEGACY_HEAD}],
        "users": [
            {"id": 1, "username": "admin", "password_hash": "x", "display_name": "관리자", "role": "admin",
             "created_at": TS, "must_change_password": 0, "token_version": 0},
            {"id": 2, "username": "qa", "password_hash": "y", "display_name": "QA", "role": "user",
             "created_at": "2026-03-16 11:18:16", "must_change_password": 1, "token_version": 3},
        ],
        "projects": [{"id": 5, "name": "P", "description": None, "jira_base_url": None, "created_by": 1,
                      "created_at": TS, "updated_at": TS, "is_private": 0,
                      "field_config": '{"hidden": ["r1"]}', "issue_tracker": None}],
        "project_members": [{"id": 1, "project_id": 5, "user_id": 2, "role": "tester", "added_at": TS}],
        "test_case_sheets": [
            {"id": 1, "project_id": 5, "name": "기능", "sort_order": 0, "created_at": TS, "parent_id": None, "is_folder": 0},
        ],
        "test_cases": [
            {"id": 10, "project_id": 5, "no": 1, "tc_id": "TC-1", "sheet_name": "기능", "created_at": TS,
             "updated_at": TS, "created_by": 1, "custom_fields": None, "test_steps": "1. 실행"},
            {"id": 11, "project_id": 5, "no": 2, "tc_id": "TC-2", "sheet_name": "기능", "created_at": TS,
             "updated_at": TS, "created_by": 1, "custom_fields": "null"},
            {"id": 12, "project_id": 5, "no": 3, "tc_id": "TC-3", "sheet_name": "기능", "created_at": TS,
             "updated_at": TS, "created_by": 1, "custom_fields": '{"env": "QA", "n": 1.5}',
             "deleted_at": "2026-03-20 09:00:00.500000"},
        ],
        "test_case_history": [
            {"id": 1, "test_case_id": 10, "changed_by": 1, "changed_at": TS, "field_name": "test_steps",
             "old_value": "a", "new_value": "b"},
            {"id": 347, "test_case_id": 446, "changed_by": 1, "changed_at": TS, "field_name": "test_steps",
             "old_value": "Step 1", "new_value": "Updated step"},
        ],
        "test_runs": [{"id": 3, "project_id": 5, "name": "R", "version": "1.0", "environment": None, "round": 1,
                       "status": "completed", "created_by": 1, "created_at": TS, "completed_at": TS,
                       "test_plan_id": None, "sheet_names": '["기능"]', "compare_run_id": None}],
        "test_results": [
            {"id": 7, "test_run_id": 3, "test_case_id": 10, "result": "PASS", "executed_by": 1,
             "executed_at": TS, "duration_sec": 0.1},
            {"id": 8, "test_run_id": 3, "test_case_id": 12, "result": "NS", "executed_by": 1},
        ],
        "attachments": [{"id": 1, "test_result_id": 7, "filename": "shot.png", "filepath": "abc.png",
                         "content_type": "image/png", "file_size": 3, "uploaded_by": 1, "uploaded_at": TS}],
    }


def make_legacy_db(tmp_path, rows=None, schema=SCHEMA, name="legacy.db"):
    path = str(tmp_path / name)
    con = _create_legacy(path, schema)
    for table, items in (base_rows() if rows is None else rows).items():
        for row in items:
            cols = list(row)
            con.execute(f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)}) '
                        f'VALUES ({", ".join("?" for _ in cols)})', [row[c] for c in cols])
    con.commit()
    con.close()
    return path


# ── 대상 PostgreSQL ─────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def target_url():
    url = testing_db.create_database(prefix="ymtc_mig")
    os.environ["DATABASE_URL"] = url  # 모델 임포트용. 스크립트도 같은 값을 쓴다
    os.environ["DATABASE_URL_DIRECT"] = ""
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    yield url
    testing_db.drop_database(url)


@pytest.fixture
def dst(target_url):
    from sqlalchemy import create_engine, text

    eng = create_engine(target_url)
    with eng.begin() as conn:
        tables = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
        )).scalars().all()
        conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
    yield eng
    eng.dispose()


@pytest.fixture
def mig(target_url):
    import migrate_sqlite_to_pg
    return migrate_sqlite_to_pg


def _problems(mig, src_path, dst, allow=frozenset({("test_case_history", 347)})):
    with pytest.raises(mig.MigrationError) as e:
        mig.precheck(mig.open_source(src_path), dst, set(allow))
    return "\n".join(e.value.problems)


# ── Task 1: 사전 점검 ───────────────────────────────────────────────────────

def test_정상_원본은_통과하고_허용한_고아만_제외한다(tmp_path, dst, mig):
    pre = mig.precheck(mig.open_source(make_legacy_db(tmp_path)), dst, {("test_case_history", 347)})
    assert pre.excluded == {"test_case_history": {347}}
    assert pre.excluded_rows["test_case_history"][0]["test_case_id"] == 446


def test_원본은_읽기_전용으로_열린다(tmp_path, mig):
    con = mig.open_source(make_legacy_db(tmp_path))
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM users")


def test_legacy_head_가_아니면_멈춘다(tmp_path, dst, mig):
    rows = base_rows()
    rows["alembic_version"] = [{"version_num": "0001_pg_baseline"}]
    assert "5e0b8c2d4f17" in _problems(mig, make_legacy_db(tmp_path, rows), dst)


def test_칸_구성이_다르면_차이를_적고_멈춘다(tmp_path, dst, mig):
    schema = json.loads(json.dumps(SCHEMA))
    schema["users"]["columns"].append(["nickname", "VARCHAR(10)", False, 0])
    schema["projects"]["columns"] = [c for c in schema["projects"]["columns"] if c[0] != "issue_tracker"]
    rows = base_rows()
    rows["projects"][0].pop("issue_tracker")
    msg = _problems(mig, make_legacy_db(tmp_path, rows, schema), dst)
    assert "users" in msg and "nickname" in msg
    assert "projects" in msg and "issue_tracker" in msg


def test_허용하지_않은_고아가_있으면_목록을_내고_멈춘다(tmp_path, dst, mig):
    rows = base_rows()
    rows["test_results"].append({"id": 9, "test_run_id": 3, "test_case_id": 999, "result": "FAIL", "executed_by": 1})
    msg = _problems(mig, make_legacy_db(tmp_path, rows), dst)
    assert "test_results" in msg and "9" in msg


def test_허용한_고아가_원본에_없으면_멈춘다(tmp_path, dst, mig):
    msg = _problems(mig, make_legacy_db(tmp_path), dst,
                    allow={("test_case_history", 347), ("test_case_history", 5)})
    assert "test_case_history:5" in msg


@pytest.mark.parametrize("table, idx, col, bad, word", [
    ("users", 0, "must_change_password", 2, "must_change_password"),
    ("test_results", 0, "result", "OK", "result"),
    ("users", 0, "role", "ADMIN", "role"),
    ("test_cases", 0, "tc_id", "X" * 51, "tc_id"),
    ("test_cases", 0, "custom_fields", "{not json", "custom_fields"),
    ("test_runs", 0, "created_at", "어제", "created_at"),
])
def test_값_규칙을_어기면_멈춘다(tmp_path, dst, mig, table, idx, col, bad, word):
    rows = base_rows()
    rows[table][idx][col] = bad
    assert word in _problems(mig, make_legacy_db(tmp_path, rows), dst)


def test_대상이_비어_있지_않으면_멈춘다(tmp_path, dst, mig):
    from sqlalchemy import text

    with dst.begin() as conn:
        conn.execute(text("INSERT INTO users (username, password_hash, display_name, role, must_change_password, "
                          "token_version) VALUES ('x', 'x', 'x', 'user', false, 0)"))
    assert "users" in _problems(mig, make_legacy_db(tmp_path), dst)


# ── Task 2: 복사와 시퀀스 ───────────────────────────────────────────────────

def _copy(mig, src_path, dst, allow=frozenset({("test_case_history", 347)})):
    src = mig.open_source(src_path)
    pre = mig.precheck(src, dst, set(allow))
    with dst.begin() as conn:
        counts = mig.copy_all(src, conn, pre.excluded)
        mig.fix_sequences(conn)
    return counts


def _q(dst, sql, **kw):
    from sqlalchemy import text
    with dst.connect() as conn:
        return conn.execute(text(sql), kw).all()


def test_id_를_보존하고_제외_행은_빼고_넣는다(tmp_path, dst, mig):
    counts = _copy(mig, make_legacy_db(tmp_path), dst)
    assert counts["test_case_history"] == 1 and counts["test_cases"] == 3
    assert _q(dst, "SELECT id FROM test_case_history") == [(1,)]
    assert [r[0] for r in _q(dst, "SELECT id FROM test_cases ORDER BY id")] == [10, 11, 12]
    assert _q(dst, "SELECT test_case_id FROM test_results WHERE id = 7") == [(10,)]


def test_custom_fields_는_SQL_NULL_과_JSON_null_과_객체를_구분해_옮긴다(tmp_path, dst, mig):
    _copy(mig, make_legacy_db(tmp_path), dst)
    rows = dict(_q(dst, "SELECT id, json_typeof(custom_fields) FROM test_cases"))
    assert rows == {10: None, 11: "null", 12: "object"}
    assert _q(dst, "SELECT custom_fields->>'env' FROM test_cases WHERE id = 12") == [("QA",)]
    assert _q(dst, "SELECT json_typeof(sheet_names) FROM test_runs") == [("array",)]


def test_불리언_시각_enum_은_타입에_맞게_들어간다(tmp_path, dst, mig):
    from datetime import datetime
    _copy(mig, make_legacy_db(tmp_path), dst)
    assert _q(dst, "SELECT must_change_password, token_version FROM users WHERE id = 2") == [(True, 3)]
    assert _q(dst, "SELECT deleted_at FROM test_cases WHERE id = 12") == [(datetime(2026, 3, 20, 9, 0, 0, 500000),)]
    assert _q(dst, "SELECT result::text FROM test_results ORDER BY id") == [("PASS",), ("NS",)]


def test_자기_참조는_부모가_뒤_id_여도_들어간다(tmp_path, dst, mig):
    rows = base_rows()
    rows["test_case_sheets"] = [
        {"id": 1, "project_id": 5, "name": "자식", "sort_order": 0, "created_at": TS, "parent_id": 2, "is_folder": 0},
        {"id": 2, "project_id": 5, "name": "폴더", "sort_order": 1, "created_at": TS, "parent_id": None, "is_folder": 1},
    ]
    rows["test_runs"].append(dict(rows["test_runs"][0], id=4, round=2, compare_run_id=6))
    rows["test_runs"].append(dict(rows["test_runs"][0], id=6, round=3, compare_run_id=None))
    _copy(mig, make_legacy_db(tmp_path, rows), dst)
    assert _q(dst, "SELECT parent_id FROM test_case_sheets WHERE id = 1") == [(2,)]
    assert _q(dst, "SELECT compare_run_id FROM test_runs WHERE id = 4") == [(6,)]


def test_시퀀스는_다음_id_가_max_더하기_1_빈_테이블은_1(tmp_path, dst, mig):
    _copy(mig, make_legacy_db(tmp_path), dst)
    with dst.begin() as conn:
        from sqlalchemy import text
        tc = conn.execute(text("INSERT INTO test_case_sheets (project_id, name, sort_order, is_folder) "
                               "VALUES (5, 'new', 9, false) RETURNING id")).scalar()
        plan = conn.execute(text("INSERT INTO test_plans (project_id, name, created_by) "
                                 "VALUES (5, 'p', 1) RETURNING id")).scalar()
    assert (tc, plan) == (2, 1)


def test_중간에_실패하면_대상은_빈_채로_남는다(tmp_path, dst, mig, monkeypatch):
    src_path = make_legacy_db(tmp_path)
    src = mig.open_source(src_path)
    pre = mig.precheck(src, dst, {("test_case_history", 347)})
    real = mig._insert_rows
    calls = {"n": 0}

    def boom(conn, table, cols, rows):
        calls["n"] += 1
        if calls["n"] == 3:
            raise RuntimeError("강제 실패")
        return real(conn, table, cols, rows)

    monkeypatch.setattr(mig, "_insert_rows", boom)
    with pytest.raises(RuntimeError):
        with dst.begin() as conn:
            mig.copy_all(src, conn, pre.excluded)
    assert _q(dst, "SELECT count(*) FROM users") == [(0,)]
    assert _q(dst, "SELECT count(*) FROM projects") == [(0,)]
