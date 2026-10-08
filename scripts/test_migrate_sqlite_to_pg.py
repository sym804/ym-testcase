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


# ── Task 3: 독립 검증 ───────────────────────────────────────────────────────

def _copied(mig, tmp_path, dst):
    src = mig.open_source(make_legacy_db(tmp_path))
    pre = mig.precheck(src, dst, {("test_case_history", 347)})
    with dst.begin() as conn:
        mig.copy_all(src, conn, pre.excluded)
        mig.fix_sequences(conn)
    return src, pre


def _verify(mig, src, pre, dst):
    with dst.connect() as conn:
        return mig.verify(src, conn, pre.excluded)


def _tamper(dst, sql):
    from sqlalchemy import text
    with dst.begin() as conn:
        conn.execute(text(sql))


def test_그대로_옮긴_결과는_불일치가_없다(tmp_path, dst, mig):
    src, pre = _copied(mig, tmp_path, dst)
    assert _verify(mig, src, pre, dst) == []


@pytest.mark.parametrize("sql, word", [
    ("DELETE FROM attachments", "attachments"),
    ("UPDATE test_cases SET tc_id = 'TC-9' WHERE id = 10", "test_cases.tc_id"),
    ("UPDATE test_cases SET deleted_at = '2026-03-20 09:00:00.5001' WHERE id = 12", "test_cases.deleted_at"),
    ("UPDATE users SET must_change_password = false WHERE id = 2", "users.must_change_password"),
    ("UPDATE test_cases SET custom_fields = to_json('{\"env\": \"QA\", \"n\": 1.5}'::text) WHERE id = 12",
     "test_cases.custom_fields"),
    ("UPDATE test_cases SET custom_fields = NULL WHERE id = 11", "test_cases.custom_fields"),
    ("UPDATE test_cases SET custom_fields = 'null'::json WHERE id = 10", "test_cases.custom_fields"),
    ("UPDATE test_results SET duration_sec = 0.2 WHERE id = 7", "test_results.duration_sec"),
    ("SELECT setval(pg_get_serial_sequence('users', 'id'), 3, true)", "users"),
    ("SELECT setval(pg_get_serial_sequence('test_plans', 'id'), 1, true)", "test_plans"),
])
def test_검증기는_틀린_대상을_잡는다(tmp_path, dst, mig, sql, word):
    src, pre = _copied(mig, tmp_path, dst)
    _tamper(dst, sql)
    problems = _verify(mig, src, pre, dst)
    assert any(word in p for p in problems), problems


# ── Task 4: 첨부 이관과 실행 진입점 ─────────────────────────────────────────

PNG_BYTES = b"\x89PNG-test"


def _uploads(tmp_path, files):
    d = tmp_path / "uploads"
    d.mkdir(exist_ok=True)
    for name, data in files.items():
        (d / name).write_bytes(data)
    return str(d)


def _committed(mig, tmp_path, dst):
    _copied(mig, tmp_path, dst)


def test_첨부를_새_키로_올리고_해시를_대조한_뒤_filepath_를_바꾼다(tmp_path, dst, mig):
    from services.storage import LocalStorage
    _committed(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES, "orphan.png": b"x", "old.jpg": b"y", ".gitkeep": b""})
    st = LocalStorage(str(tmp_path / "store"))
    with dst.begin() as conn:
        rep = mig.migrate_attachments(conn, up, st)
    assert rep.moved == [1] and rep.skipped_same == []
    assert rep.orphan_files == ["old.jpg", "orphan.png"]
    assert _q(dst, "SELECT filepath FROM attachments WHERE id = 1") == [("attachments/abc.png",)]
    assert st.read("attachments/abc.png", 100) == PNG_BYTES
    assert os.path.exists(os.path.join(up, "abc.png")), "원본 파일을 지우면 안 된다"


def test_다시_실행하면_건너뛴다(tmp_path, dst, mig):
    from services.storage import LocalStorage
    _committed(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    st = LocalStorage(str(tmp_path / "store"))
    with dst.begin() as conn:
        mig.migrate_attachments(conn, up, st)
    with dst.begin() as conn:
        rep = mig.migrate_attachments(conn, up, st)
    assert rep.moved == [] and rep.skipped_same == [1]


def test_같은_키에_다른_내용이_있으면_멈춘다(tmp_path, dst, mig):
    from services.storage import LocalStorage
    _committed(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    st = LocalStorage(str(tmp_path / "store"))
    st.put("attachments/abc.png", b"different", "image/png")
    with pytest.raises(mig.MigrationError, match="abc.png"):
        with dst.begin() as conn:
            mig.migrate_attachments(conn, up, st)
    assert _q(dst, "SELECT filepath FROM attachments WHERE id = 1") == [("abc.png",)]


def test_행은_있는데_파일이_없으면_멈춘다(tmp_path, dst, mig):
    from services.storage import LocalStorage
    _committed(mig, tmp_path, dst)
    up = _uploads(tmp_path, {})
    with pytest.raises(mig.MigrationError, match="abc.png"):
        with dst.begin() as conn:
            mig.migrate_attachments(conn, up, LocalStorage(str(tmp_path / "store")))


def _argv(src, url, *extra):
    return ["--source", src, "--target", url, "--allow-orphan", "test_case_history:347", *extra]


def test_dry_run_은_검증까지_하고_되돌린다(tmp_path, dst, mig, target_url):
    out = tmp_path / "excluded.json"
    code = mig.main(_argv(make_legacy_db(tmp_path), target_url, "--dry-run", "--excluded-out", str(out)))
    assert code == 0
    assert _q(dst, "SELECT count(*) FROM test_cases") == [(0,)]
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["test_case_history"][0]["id"] == 347


def test_실행하면_데이터와_첨부를_옮긴다(tmp_path, dst, mig, target_url, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "store"))
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    code = mig.main(_argv(make_legacy_db(tmp_path), target_url, "--uploads", up, "--storage", "local",
                          "--excluded-out", str(tmp_path / "ex.json")))
    assert code == 0
    assert _q(dst, "SELECT count(*) FROM test_cases") == [(3,)]
    assert _q(dst, "SELECT filepath FROM attachments") == [("attachments/abc.png",)]


def test_첨부가_있는데_uploads_를_안_주면_아무것도_쓰지_않고_멈춘다(tmp_path, dst, mig, target_url):
    code = mig.main(_argv(make_legacy_db(tmp_path), target_url, "--excluded-out", str(tmp_path / "ex.json")))
    assert code == 1
    assert _q(dst, "SELECT count(*) FROM users") == [(0,)]


def test_점검에_걸리면_종료코드_1_이고_대상은_비어_있다(tmp_path, dst, mig, target_url):
    code = mig.main(["--source", make_legacy_db(tmp_path), "--target", target_url, "--dry-run",
                     "--excluded-out", str(tmp_path / "ex.json")])
    assert code == 1
    assert _q(dst, "SELECT count(*) FROM users") == [(0,)]


def test_첨부_단계만_다시_돌릴_수_있다(tmp_path, dst, mig, target_url, monkeypatch):
    """데이터 커밋 뒤 첨부 단계가 실패하면, 대상이 이미 차 있어 전체 재실행은 사전 점검에서 막힌다."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "store"))
    src = make_legacy_db(tmp_path)
    empty = _uploads(tmp_path, {})
    assert mig.main(_argv(src, target_url, "--uploads", empty, "--storage", "local",
                          "--excluded-out", str(tmp_path / "ex.json"))) == 1
    assert _q(dst, "SELECT filepath FROM attachments") == [("abc.png",)]  # 데이터는 들어갔고 첨부만 남았다

    (tmp_path / "uploads" / "abc.png").write_bytes(PNG_BYTES)
    assert mig.main(["--source", src, "--target", target_url, "--uploads", str(tmp_path / "uploads"),
                     "--storage", "local", "--attachments-only"]) == 0
    assert _q(dst, "SELECT filepath FROM attachments") == [("attachments/abc.png",)]


# ── QA 2인 지적 (Codex) ─────────────────────────────────────────────────────

def test_dry_run_은_시퀀스도_건드리지_않는다(tmp_path, dst, mig, target_url):
    """setval 은 트랜잭션을 되돌려도 남는다(실측). dry-run 뒤 다음 id 가 1 이어야 한다."""
    assert mig.main(_argv(make_legacy_db(tmp_path), target_url, "--dry-run",
                          "--excluded-out", str(tmp_path / "ex.json"))) == 0
    assert _q(dst, "SELECT last_value, is_called FROM users_id_seq") == [(1, False)]
    assert _q(dst, "SELECT last_value, is_called FROM test_cases_id_seq") == [(1, False)]


def test_첨부만_다시_돌리기와_dry_run_은_같이_쓸_수_없다(tmp_path, dst, mig, target_url, monkeypatch):
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "store"))
    _copied(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    code = mig.main(["--source", make_legacy_db(tmp_path, name="b.db"), "--target", target_url,
                     "--uploads", up, "--attachments-only", "--dry-run"])
    assert code == 1
    assert not (tmp_path / "store").exists()
    assert _q(dst, "SELECT filepath FROM attachments") == [("abc.png",)]


class _BlindStorage:
    """HEAD 가 400 이거나 Content-Length 가 없어 size() 가 늘 None 인 저장소."""

    def __init__(self, objects):
        self.objects = dict(objects)

    def size(self, key):
        return None

    def read(self, key, max_bytes):
        return self.objects[key]

    def put(self, key, data, content_type):
        self.objects[key] = data

    def put_new(self, key, data, content_type):
        from services.storage import StorageConflict
        if key in self.objects:
            raise StorageConflict(key)
        self.objects[key] = data


def test_존재_판정이_안_되는_저장소에서도_다른_내용을_덮어쓰지_않는다(tmp_path, dst, mig):
    _copied(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    st = _BlindStorage({"attachments/abc.png": b"someone else"})
    with pytest.raises(mig.MigrationError, match="abc.png"):
        with dst.begin() as conn:
            mig.migrate_attachments(conn, up, st)
    assert st.objects["attachments/abc.png"] == b"someone else"


def test_존재_판정이_안_되는_저장소에서_같은_내용이면_건너뛴다(tmp_path, dst, mig):
    _copied(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    st = _BlindStorage({"attachments/abc.png": PNG_BYTES})
    with dst.begin() as conn:
        rep = mig.migrate_attachments(conn, up, st)
    assert rep.skipped_same == [1]


@pytest.mark.parametrize("table, col, bad", [
    ("test_cases", "no", "oops"),
    ("test_cases", "no", 2147483648),
    ("test_results", "duration_sec", "abc"),
    ("test_results", "duration_sec", float("inf")),
    ("test_cases", "custom_fields", '{"a": NaN}'),
    ("test_cases", "created_at", "2026-03-16"),
    ("test_cases", "created_at", "2026-03-16T11:18:16+09:00"),
    ("test_cases", "created_at", "2026-03-16 11:18:16.1234567"),
])
def test_숫자_시각_JSON_변형도_사전에_막는다(tmp_path, dst, mig, table, col, bad):
    rows = base_rows()
    rows[table][0][col] = bad
    assert col in _problems(mig, make_legacy_db(tmp_path, rows), dst)


def test_T_구분자_시각은_받아서_그대로_옮긴다(tmp_path, dst, mig):
    rows = base_rows()
    rows["test_cases"][0]["created_at"] = "2026-03-16T11:18:16.5"
    src = mig.open_source(make_legacy_db(tmp_path, rows))
    pre = mig.precheck(src, dst, {("test_case_history", 347)})
    with dst.begin() as conn:
        mig.copy_all(src, conn, pre.excluded)
        mig.fix_sequences(conn)
    with dst.connect() as conn:
        assert mig.verify(src, conn, pre.excluded) == []


def test_검증기는_JSON_의_true_가_1_로_바뀐_것을_잡는다(tmp_path, dst, mig):
    rows = base_rows()
    rows["test_cases"][2]["custom_fields"] = '{"flag": true, "n": 0}'
    src = mig.open_source(make_legacy_db(tmp_path, rows))
    pre = mig.precheck(src, dst, {("test_case_history", 347)})
    with dst.begin() as conn:
        mig.copy_all(src, conn, pre.excluded)
        mig.fix_sequences(conn)
    _tamper(dst, "UPDATE test_cases SET custom_fields = '{\"flag\": 1, \"n\": false}'::json WHERE id = 12")
    with dst.connect() as conn:
        problems = mig.verify(src, conn, pre.excluded)
    assert any("test_cases.custom_fields" in p for p in problems), problems


def test_검증기는_연관_테이블_변조를_잡는다(tmp_path, dst, mig):
    rows = base_rows()
    rows["run_issues"] = [{"id": 1, "test_run_id": 3, "issue_key": "X-1", "title": "t", "url": "u", "created_by": 1, "created_at": TS}]
    rows["run_issue_test_cases"] = [{"run_issue_id": 1, "test_case_id": 10}]
    src = mig.open_source(make_legacy_db(tmp_path, rows))
    pre = mig.precheck(src, dst, {("test_case_history", 347)})
    with dst.begin() as conn:
        mig.copy_all(src, conn, pre.excluded)
        mig.fix_sequences(conn)
    _tamper(dst, "UPDATE run_issue_test_cases SET test_case_id = 11")
    with dst.connect() as conn:
        assert any("run_issue_test_cases" in p for p in mig.verify(src, conn, pre.excluded))


def test_대상에_필요한_테이블이_없으면_멈춘다(tmp_path, dst, mig):
    _tamper(dst, "ALTER TABLE saved_filters RENAME TO saved_filters_away")
    try:
        assert "saved_filters" in _problems(mig, make_legacy_db(tmp_path), dst)
    finally:
        _tamper(dst, "ALTER TABLE saved_filters_away RENAME TO saved_filters")


def test_대상에_모델_밖_테이블이_차_있어도_멈춘다(tmp_path, dst, mig):
    _tamper(dst, "CREATE TABLE zz_extra (id int); INSERT INTO zz_extra VALUES (1)")
    try:
        assert "zz_extra" in _problems(mig, make_legacy_db(tmp_path), dst)
    finally:
        _tamper(dst, "DROP TABLE zz_extra")


def test_데이터_커밋_뒤_저장소_장애면_복구_명령을_안내한다(tmp_path, dst, mig, target_url, monkeypatch, capsys):
    from services import storage as storage_mod

    class Down:
        def size(self, key):
            raise storage_mod.StorageUnavailable("storage HEAD failed: HTTP 503")

        def put_new(self, key, data, content_type):
            raise storage_mod.StorageUnavailable("storage POST failed: HTTP 503")

        put = put_new

        def read(self, key, max_bytes):
            raise storage_mod.StorageUnavailable("storage GET failed: HTTP 503")

    monkeypatch.setattr(storage_mod, "get_storage", lambda: Down())
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    code = mig.main(_argv(make_legacy_db(tmp_path), target_url, "--uploads", up, "--storage", "local",
                          "--excluded-out", str(tmp_path / "ex.json")))
    assert code == 1
    assert "--attachments-only" in capsys.readouterr().err
    assert _q(dst, "SELECT count(*) FROM test_cases") == [(3,)]



# ── QA 2인 지적 (QA2) ───────────────────────────────────────────────────────

def test_첨부가_있는데_저장소를_안_정하면_아무것도_쓰지_않고_멈춘다(tmp_path, dst, mig, target_url, capsys):
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    code = mig.main(_argv(make_legacy_db(tmp_path), target_url, "--uploads", up,
                          "--excluded-out", str(tmp_path / "ex.json")))
    assert code == 1 and "--storage" in capsys.readouterr().err
    assert _q(dst, "SELECT count(*) FROM users") == [(0,)]


def test_supabase_저장소는_대상_DB_와_같은_프로젝트여야_한다(tmp_path, dst, mig, target_url, monkeypatch, capsys):
    """리허설 대상(임시 프로젝트)에 이관하면서 첨부를 운영 버킷에 올리는 사고를 막는다."""
    monkeypatch.setenv("SUPABASE_URL", "https://prodref123.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "k")
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    code = mig.main(_argv(make_legacy_db(tmp_path), target_url, "--uploads", up, "--storage", "supabase",
                          "--excluded-out", str(tmp_path / "ex.json")))
    assert code == 1 and "prodref123" in capsys.readouterr().err
    assert _q(dst, "SELECT count(*) FROM users") == [(0,)]


def test_supabase_프로젝트_ref_판정(mig):
    assert mig.supabase_ref("https://abcd1234.supabase.co") == "abcd1234"
    assert mig.target_matches_ref("postgresql+psycopg2://postgres:pw@db.abcd1234.supabase.co:5432/postgres", "abcd1234")
    assert mig.target_matches_ref(
        "postgresql+psycopg2://postgres.abcd1234:pw@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres", "abcd1234")
    assert not mig.target_matches_ref("postgresql+psycopg2://postgres.zzzz:pw@aws-0.pooler.supabase.com/postgres", "abcd1234")


def test_원본은_한_시점의_스냅샷으로_읽는다(tmp_path, mig):
    """이관 중 원본에 쓰기가 들어와도 점검·복사·검증이 같은 데이터를 본다."""
    path = make_legacy_db(tmp_path)
    src = mig.open_source(path)
    before = src.execute("SELECT count(*) FROM users").fetchone()[0]
    w = sqlite3.connect(path, timeout=0.2)
    try:
        w.execute("INSERT INTO users (id, username, password_hash, display_name, role, must_change_password, "
                  "token_version) VALUES (99, 'late', 'x', 'x', 'user', 0, 0)")
        w.commit()
    except sqlite3.OperationalError:
        pass  # 읽기 트랜잭션이 쓰기를 막은 경우도 통과
    finally:
        w.close()
    assert src.execute("SELECT count(*) FROM users").fetchone()[0] == before


def test_id_없는_테이블의_고아는_제외할_수_없다고_알린다(tmp_path, dst, mig):
    rows = base_rows()
    rows["run_issues"] = [{"id": 1, "test_run_id": 3, "issue_key": "X-1", "title": "t", "url": "u",
                           "created_by": 1, "created_at": TS}]
    rows["run_issue_test_cases"] = [{"run_issue_id": 1, "test_case_id": 999}]
    msg = _problems(mig, make_legacy_db(tmp_path, rows), dst,
                    allow={("test_case_history", 347), ("run_issue_test_cases", 1)})
    assert "run_issue_test_cases" in msg


def test_대상_제약에_걸리면_문장으로_알리고_대상은_비어_있다(tmp_path, dst, mig, target_url, capsys):
    rows = base_rows()
    rows["test_case_sheets"].append(dict(rows["test_case_sheets"][0], id=2))  # 같은 프로젝트에 같은 시트 이름
    code = mig.main(_argv(make_legacy_db(tmp_path, rows), target_url, "--dry-run",
                          "--excluded-out", str(tmp_path / "ex.json")))
    err = capsys.readouterr().err
    assert code == 1 and "Traceback" not in err and "test_case_sheets" in err
    assert _q(dst, "SELECT count(*) FROM users") == [(0,)]


def test_로컬_저장소가_uploads_와_같은_폴더면_재실행_때_새_키를_고아로_보지_않는다(tmp_path, dst, mig):
    from services.storage import LocalStorage
    _copied(mig, tmp_path, dst)
    up = _uploads(tmp_path, {"abc.png": PNG_BYTES})
    st = LocalStorage(up)  # 로컬 앱은 backend/uploads 를 저장소 루트로 쓴다
    with dst.begin() as conn:
        mig.migrate_attachments(conn, up, st)
    with dst.begin() as conn:
        rep = mig.migrate_attachments(conn, up, st)
    assert rep.orphan_files == []
