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


# ── 복사 ─────────────────────────────────────────────────────────────────────

def _is_json(col) -> bool:
    from sqlalchemy import JSON
    return isinstance(col.type, JSON)


def _convert(col, value):
    """원본 값을 대상 칸에 넣을 값으로. 값 규칙은 사전 점검이 이미 확인했다."""
    from sqlalchemy import Boolean, DateTime

    if value is None:
        return None
    if isinstance(col.type, Boolean):
        return bool(value)
    if isinstance(col.type, DateTime):
        return datetime.fromisoformat(value)
    # JSON 칸은 원문 텍스트를 그대로 넘겨 SQL 에서 CAST 한다. 파이썬 객체로 바꿔 다시 인코딩하면
    # 'null' 과 SQL NULL 의 구분이 흐려지고, 문자열을 넘기면 JSON 문자열로 이중 인코딩된다.
    return value


def _insert_rows(conn, table, cols, rows) -> None:
    from sqlalchemy import text

    if not rows:
        return
    names = ", ".join(f'"{c.name}"' for c in cols)
    params = ", ".join(f"CAST(:p{i} AS json)" if _is_json(c) else f":p{i}" for i, c in enumerate(cols))
    stmt = text(f'INSERT INTO "{table.name}" ({names}) VALUES ({params})')
    conn.execute(stmt, [{f"p{i}": v for i, v in enumerate(r)} for r in rows])


def _self_ref_columns(table) -> list:
    return [c for c in table.columns if any(fk.column.table is table for fk in c.foreign_keys)]


def copy_all(src, conn, excluded: dict) -> dict:
    """FK 순서로 옮긴다. id 는 원본 그대로. 자기 참조 칸은 비워 넣은 뒤 마지막에 채운다.

    트랜잭션은 부른 쪽이 갖는다. 중간에 실패하면 부른 쪽이 되돌려 대상은 빈 채로 남는다.
    """
    from sqlalchemy import text

    src_tables = set(_source_tables(src)) - SOURCE_ONLY
    counts, deferred = {}, []
    for table in metadata().sorted_tables:
        if table.name not in src_tables:
            continue
        src_cols = {r[1] for r in src.execute(f'PRAGMA table_info("{table.name}")')}
        cols = [c for c in table.columns if c.name in src_cols]
        self_ref = {c.name for c in _self_ref_columns(table)}
        has_id = "id" in src_cols
        skip = excluded.get(table.name, set())
        rows, later = [], []
        order = "id" if has_id else "rowid"
        for r in src.execute(f'SELECT * FROM "{table.name}" ORDER BY {order}'):
            if has_id and r["id"] in skip:
                continue
            rows.append([None if c.name in self_ref else _convert(c, r[c.name]) for c in cols])
            for name in self_ref:
                if r[name] is not None:
                    later.append((name, r["id"], r[name]))
        _insert_rows(conn, table, cols, rows)
        counts[table.name] = len(rows)
        deferred += [(table.name, *x) for x in later]
    for table_name, col, row_id, value in deferred:
        conn.execute(text(f'UPDATE "{table_name}" SET "{col}" = :v WHERE id = :i'), {"v": value, "i": row_id})
    return counts


def fix_sequences(conn) -> None:
    """다음 id 가 max(id)+1 이 되게 한다. 빈 테이블은 1 부터. is_called 를 빠뜨리면 하나 건너뛴다."""
    from sqlalchemy import text

    for table in metadata().sorted_tables:
        if "id" not in table.columns:
            continue
        seq = conn.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}).scalar()
        if not seq:
            continue
        top = conn.execute(text(f'SELECT max(id) FROM "{table.name}"')).scalar()
        if top is None:
            conn.execute(text("SELECT setval(:s, 1, false)"), {"s": seq})
        else:
            conn.execute(text("SELECT setval(:s, :v, true)"), {"s": seq, "v": top})


# ── 독립 검증 ────────────────────────────────────────────────────────────────
# 복사 쪽 변환 함수(_convert, _insert_rows)를 쓰지 않는다. 같은 변환으로 만든 값끼리 비교하면
# 변환의 버그(예: JSON 이중 인코딩)가 그대로 통과한다. 대상은 DB 가 내는 ::text 로 읽고,
# 원본 원문에서 그 텍스트가 어떻게 나와야 하는지를 대상 칸의 실제 DB 타입으로 따로 만든다.

def _expected_timestamp_text(raw: str) -> str:
    """PostgreSQL timestamp 의 텍스트는 소수 끝의 0 을 지우고, 소수가 0 이면 점째 뺀다."""
    s = raw.replace("T", " ")
    if "." not in s:
        return s
    head, frac = s.split(".", 1)
    frac = frac.rstrip("0")
    return head + ("." + frac if frac else "")


def _same(data_type: str, raw, got) -> bool:
    if raw is None or got is None:
        return raw is None and got is None
    if data_type == "boolean":
        return {0: "false", 1: "true"}.get(raw) == got
    if data_type.startswith("timestamp"):
        return _expected_timestamp_text(raw) == got
    if data_type in ("json", "jsonb"):
        return json.loads(raw) == json.loads(got)
    if data_type in ("double precision", "real", "numeric"):
        return float(raw) == float(got)
    return str(raw) == got


def verify(src, conn, excluded: dict) -> list[str]:
    """불일치 사유 목록. 비어 있으면 통과."""
    from sqlalchemy import text

    types = {(t, c): d for t, c, d in conn.execute(text(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = 'public'"))}
    target_tables = {t for t, _ in types}
    problems = []
    for table in sorted(set(_source_tables(src)) - SOURCE_ONLY):
        if table not in target_tables:
            problems.append(f"{table}: 대상에 테이블이 없습니다")
            continue
        cols = [r[1] for r in src.execute(f'PRAGMA table_info("{table}")')]
        skip = excluded.get(table, set())
        src_rows = [r for r in src.execute(f'SELECT * FROM "{table}"')
                    if not ("id" in cols and r["id"] in skip)]
        select = ", ".join(f'"{c}"::text' for c in cols)
        tgt_rows = conn.execute(text(f'SELECT {select} FROM "{table}"')).all()
        if len(src_rows) != len(tgt_rows):
            problems.append(f"{table}: 행 수가 다릅니다. 원본 {len(src_rows)}(제외 {len(skip)}행 뺀 값) 대상 {len(tgt_rows)}")
        if "id" not in cols:
            want = sorted(tuple(str(r[c]) for c in cols) for r in src_rows)
            have = sorted(tuple(r) for r in tgt_rows)
            if want != have:
                problems.append(f"{table}: 행 내용이 다릅니다")
            continue
        idx = cols.index("id")
        tgt = {int(r[idx]): r for r in tgt_rows}
        missing = [r["id"] for r in src_rows if r["id"] not in tgt]
        if missing:
            problems.append(f"{table}: 대상에 없는 id {missing[:_SAMPLE]}")
        for i, c in enumerate(cols):
            dtype = types.get((table, c))
            if dtype is None:
                problems.append(f"{table}.{c}: 대상에 칸이 없습니다")
                continue
            bad = [(r["id"], r[c], tgt[r["id"]][i]) for r in src_rows
                   if r["id"] in tgt and not _same(dtype, r[c], tgt[r["id"]][i])]
            if bad:
                problems.append(f"{table}.{c}: {len(bad)}건 다릅니다. 예 {bad[:2]}")
    problems += _verify_sequences(conn, target_tables)
    return problems


def _verify_sequences(conn, tables) -> list[str]:
    from sqlalchemy import text

    problems = []
    for table in sorted(tables):
        seq = conn.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table}).scalar() \
            if conn.execute(text("SELECT 1 FROM information_schema.columns WHERE table_schema = 'public' "
                                 "AND table_name = :t AND column_name = 'id'"), {"t": table}).first() else None
        if not seq:
            continue
        last, called = conn.execute(text(f"SELECT last_value, is_called FROM {seq}")).one()
        top = conn.execute(text(f'SELECT max(id) FROM "{table}"')).scalar()
        want = (top, True) if top is not None else (1, False)
        if (last, called) != want:
            nxt = last + 1 if called else last
            problems.append(f"{table}: 시퀀스 다음 값이 {nxt} 입니다. {(top or 0) + 1} 이어야 합니다")
    return problems
