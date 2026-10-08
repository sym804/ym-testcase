"""SQLite(v1.10.3.1, legacy head 5e0b8c2d4f17) 데이터를 PostgreSQL 로 옮긴다. 일회성.

    python scripts/migrate_sqlite_to_pg.py --source <tc_manager.db> --target <postgresql+psycopg2://...>
        [--uploads <backend/uploads>] [--allow-orphan test_case_history:347] [--dry-run]
        [--excluded-out excluded_rows.json]

순서: 사전 점검 -> 복사(한 트랜잭션) -> 독립 검증 -> 커밋 -> 첨부를 Storage 로.
대상은 미리 `alembic upgrade head` 로 기준점 스키마를 올려 둔 빈 DB 다.
--dry-run 은 점검·복사·검증까지 하고 되돌린다. 첨부는 건드리지 않는다.

원본은 읽기 전용(mode=ro)으로만 연다. 원본과 uploads 폴더를 고치거나 지우지 않는다.
"""
import json
import os
import sqlite3
import sys
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(os.path.dirname(HERE), "backend")
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

LEGACY_HEAD = "5e0b8c2d4f17"
SCHEMA_FILE = os.path.join(HERE, "legacy_schema.json")
#: 원본에만 있고 옮기지 않는 테이블. 대상의 alembic_version 은 기준점이 따로 갖는다
SOURCE_ONLY = {"alembic_version"}
_SAMPLE = 5


class MigrationError(Exception):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("\n".join(self.problems))


@dataclass
class Precheck:
    #: 옮기지 않는 행. 테이블 -> id 집합
    excluded: dict = field(default_factory=dict)
    #: 제외한 행의 원본 전체. excluded_rows.json 으로 보관한다
    excluded_rows: dict = field(default_factory=dict)


def open_source(path: str) -> sqlite3.Connection:
    """읽기 전용으로 연다. 이 연결로는 원본을 고칠 수 없다."""
    p = Path(path).resolve()
    if not p.is_file():
        raise MigrationError([f"원본 파일이 없습니다: {path}"])
    uri = "file:" + urllib.parse.quote(p.as_posix(), safe="/:") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def metadata():
    import models  # DATABASE_URL 이 있어야 임포트된다. main() 이 대상 주소로 채운다
    return models.Base.metadata


def _source_tables(src) -> list[str]:
    return [r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]


def _source_shape(src) -> dict:
    out = {}
    for t in _source_tables(src):
        cols = [[r[1], r[2], bool(r[3]), r[5]] for r in src.execute(f'PRAGMA table_info("{t}")')]
        fks = sorted([[r[3], r[2], r[4]] for r in src.execute(f'PRAGMA foreign_key_list("{t}")')])
        out[t] = {"columns": cols, "foreign_keys": fks}
    return out


def _check_version(src) -> list[str]:
    try:
        rows = [r[0] for r in src.execute("SELECT version_num FROM alembic_version")]
    except sqlite3.DatabaseError as e:
        return [f"원본에 alembic_version 이 없습니다({e}). v1.10.3.1 의 DB 가 아닙니다"]
    if rows != [LEGACY_HEAD]:
        return [f"원본 리비전이 {rows} 입니다. {LEGACY_HEAD}(v1.10.3.1) 에서만 옮깁니다. "
                "sqlite-legacy 버전으로 먼저 최신 상태로 올리세요"]
    return []


def _check_shape(src) -> list[str]:
    expected = json.load(open(SCHEMA_FILE, encoding="utf-8"))
    actual = _source_shape(src)
    problems = []
    for t in sorted(set(expected) - set(actual)):
        problems.append(f"원본에 테이블이 없습니다: {t}")
    for t in sorted(set(actual) - set(expected)):
        problems.append(f"원본에 예상 밖 테이블이 있습니다: {t}")
    for t in sorted(set(expected) & set(actual)):
        exp_cols = {c[0]: c for c in expected[t]["columns"]}
        act_cols = {c[0]: c for c in actual[t]["columns"]}
        for c in sorted(set(exp_cols) - set(act_cols)):
            problems.append(f"{t}: 칸이 없습니다: {c}")
        for c in sorted(set(act_cols) - set(exp_cols)):
            problems.append(f"{t}: 예상 밖 칸이 있습니다: {c}")
        for c in sorted(set(exp_cols) & set(act_cols)):
            if exp_cols[c] != act_cols[c]:
                problems.append(f"{t}.{c}: 칸 정의가 다릅니다. 예상 {exp_cols[c][1:]} 실제 {act_cols[c][1:]}")
        if expected[t]["foreign_keys"] != actual[t]["foreign_keys"]:
            problems.append(f"{t}: FK 가 다릅니다. 예상 {expected[t]['foreign_keys']} 실제 {actual[t]['foreign_keys']}")
    return problems


def _check_orphans(src, allow: set) -> tuple[list[str], dict]:
    problems, excluded = [], {}
    found = set()
    for table, rowid, parent, _fkid in src.execute("PRAGMA foreign_key_check"):
        found.add((table, rowid))
        if (table, rowid) in allow:
            excluded.setdefault(table, set()).add(rowid)
        else:
            problems.append(f"FK 고아: {table}:{rowid} 가 없는 {parent} 를 가리킵니다. "
                            f"옮기지 않으려면 --allow-orphan {table}:{rowid}")
    for table, rowid in sorted(allow - found):
        problems.append(f"허용한 고아가 원본에 없습니다: {table}:{rowid}")
    return problems, excluded


def _column_rule(col):
    """대상 칸 타입으로 값 규칙을 정한다. (이름, 검사 함수) 또는 None."""
    from sqlalchemy import JSON, Boolean, DateTime, Enum, String

    ty = col.type
    if isinstance(ty, Boolean):
        return "0/1", lambda v: v in (0, 1)
    if isinstance(ty, DateTime):
        def ok(v):
            try:
                datetime.fromisoformat(v)
                return isinstance(v, str)
            except (TypeError, ValueError):
                return False
        return "시각", ok
    if isinstance(ty, JSON):
        def ok(v):
            try:
                json.loads(v)
                return isinstance(v, str)
            except (TypeError, ValueError):
                return False
        return "JSON", ok
    if isinstance(ty, Enum):
        allowed = set(ty.enums)
        return f"허용 값 {sorted(allowed)}", lambda v: v in allowed
    if isinstance(ty, String) and ty.length:
        n = ty.length
        return f"{n}자 이내", lambda v: not isinstance(v, str) or len(v) <= n
    return None


def _id_of(row):
    return row["id"] if "id" in row.keys() else None


def _check_values(src, excluded: dict) -> list[str]:
    md = metadata()
    problems = []
    src_tables = set(_source_tables(src)) - SOURCE_ONLY
    for t in sorted(src_tables - set(md.tables)):
        problems.append(f"대상에 없는 테이블입니다: {t}")
    for table in md.sorted_tables:
        if table.name not in src_tables:
            continue
        src_cols = {r[1] for r in src.execute(f'PRAGMA table_info("{table.name}")')}
        for col in table.columns:
            if col.name not in src_cols:
                if not col.nullable and col.default is None and col.server_default is None:
                    problems.append(f"{table.name}.{col.name}: 원본에 없고 대상은 값이 필요합니다")
                continue
            rule = _column_rule(col)
            if rule is None:
                continue
            what, ok = rule
            bad = []
            for row in src.execute(f'SELECT * FROM "{table.name}" WHERE "{col.name}" IS NOT NULL'):
                if _id_of(row) in excluded.get(table.name, ()):
                    continue
                if not ok(row[col.name]):
                    bad.append(_id_of(row))
            if bad:
                problems.append(f"{table.name}.{col.name}: {what} 를 어긴 행 {len(bad)}건 "
                                f"(id {bad[:_SAMPLE]})")
    return problems


def _check_target(dst) -> list[str]:
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect, text

    heads = set(ScriptDirectory.from_config(Config(os.path.join(BACKEND, "alembic.ini"))).get_heads())
    problems = []
    with dst.connect() as conn:
        names = set(inspect(conn).get_table_names())
        if "alembic_version" not in names:
            return ["대상에 스키마가 없습니다. 먼저 alembic upgrade head 를 실행하세요"]
        rev = set(conn.execute(text("SELECT version_num FROM alembic_version")).scalars())
        if rev != heads:
            problems.append(f"대상 리비전 {sorted(rev)} 이 코드의 head {sorted(heads)} 와 다릅니다")
        for t in metadata().sorted_tables:
            if t.name in names:
                n = conn.execute(text(f'SELECT count(*) FROM "{t.name}"')).scalar()
                if n:
                    problems.append(f"대상 {t.name} 에 이미 {n}행이 있습니다. 빈 DB 에만 옮깁니다")
    return problems


def precheck(src, dst, allow_orphans: set) -> Precheck:
    """하나라도 걸리면 MigrationError. 대상에는 아무것도 쓰지 않는다."""
    problems = _check_version(src)
    if problems:
        raise MigrationError(problems)
    problems = _check_shape(src)
    if problems:
        raise MigrationError(problems)
    orphan_problems, excluded = _check_orphans(src, set(allow_orphans))
    problems = orphan_problems + _check_values(src, excluded) + _check_target(dst)
    if problems:
        raise MigrationError(problems)
    rows = {}
    for table, ids in excluded.items():
        rows[table] = [dict(r) for r in src.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
                       if r["id"] in ids]
    return Precheck(excluded=excluded, excluded_rows=rows)
