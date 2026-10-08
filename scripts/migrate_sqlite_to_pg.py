"""SQLite(v1.10.3.1, legacy head 5e0b8c2d4f17) 데이터를 PostgreSQL 로 옮긴다. 일회성.

    python scripts/migrate_sqlite_to_pg.py --source <tc_manager.db> --target <postgresql+psycopg2://...>
        [--uploads <backend/uploads> --storage local|supabase] [--allow-orphan test_case_history:347]
        [--dry-run] [--excluded-out excluded_rows.json]

순서: 사전 점검 -> 복사(한 트랜잭션) -> 독립 검증 -> 커밋 -> 첨부를 Storage 로.
대상은 미리 `alembic upgrade head` 로 기준점 스키마를 올려 둔 빈 DB 다.
--dry-run 은 점검·복사·검증까지 하고 되돌린다. 첨부는 건드리지 않는다.

원본은 읽기 전용(mode=ro)으로 열고, 처음부터 끝까지 한 읽기 트랜잭션(한 시점)으로 읽는다.
원본 DB 와 uploads 의 파일을 고치거나 지우지 않는다. 로컬 저장소가 uploads 와 같은 폴더면
그 안에 attachments/ 를 새로 만들어 복사본을 둔다(로컬 앱이 읽는 위치).
첨부를 올릴 저장소는 --storage 로 직접 정한다. supabase 면 SUPABASE_URL 의 프로젝트가
--target 의 프로젝트와 같아야 한다(리허설 첨부가 운영 버킷에 올라가는 사고 방지).
"""
import json
import math
import os
import re
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
    con = sqlite3.connect(uri, uri=True, isolation_level=None)
    con.row_factory = sqlite3.Row
    # 한 읽기 트랜잭션으로 연다. 점검·복사·검증이 같은 시점의 데이터를 본다. 연결을 닫을 때까지 유지한다
    con.execute("BEGIN")
    con.execute("SELECT count(*) FROM sqlite_master").fetchone()
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
        has_id = any(r[1] == "id" for r in src.execute(f'PRAGMA table_info("{table}")'))
        if (table, rowid) in allow and not has_id:
            problems.append(f"FK 고아: {table}:{rowid}. id 가 없는 테이블의 행은 제외할 수 없습니다. "
                            "원본에서 원인을 먼저 확인하세요")
        elif (table, rowid) in allow:
            excluded.setdefault(table, set()).add(rowid)
        else:
            problems.append(f"FK 고아: {table}:{rowid} 가 없는 {parent} 를 가리킵니다. "
                            f"옮기지 않으려면 --allow-orphan {table}:{rowid}")
    for table, rowid in sorted(allow - found):
        problems.append(f"허용한 고아가 원본에 없습니다: {table}:{rowid}")
    return problems, excluded


#: SQLAlchemy 가 SQLite DATETIME 에 쓰는 모양. 날짜만, 시간대 붙은 값, 7자리 이상 소수초는 받지 않는다.
#: 날짜만은 자정으로 늘어나고, 시간대는 KST naive 계약과 어긋나고, 긴 소수초는 잘린다.
_TIMESTAMP_RE = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d{1,6})?")
_INT32 = (-(2 ** 31), 2 ** 31 - 1)


def _json_ok(v) -> bool:
    if not isinstance(v, str):
        return False

    def reject(name):
        raise ValueError(name)  # NaN, Infinity: 파이썬은 받지만 PostgreSQL json 은 거부한다

    try:
        json.loads(v, parse_constant=reject)
        return True
    except ValueError:
        return False


def _column_rule(col):
    """대상 칸 타입으로 값 규칙을 정한다. (이름, 검사 함수) 또는 None."""
    from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, Integer, String

    ty = col.type
    if isinstance(ty, Boolean):
        return "0/1", lambda v: v in (0, 1) and not isinstance(v, float)
    if isinstance(ty, DateTime):
        def ok(v):
            if not isinstance(v, str) or not _TIMESTAMP_RE.fullmatch(v):
                return False
            try:
                datetime.fromisoformat(v)
                return True
            except ValueError:
                return False
        return "시각(YYYY-MM-DD HH:MM:SS[.ffffff], 시간대 없음)", ok
    if isinstance(ty, JSON):
        return "JSON(NaN/Infinity 제외)", _json_ok
    if isinstance(ty, Integer):
        lo, hi = _INT32
        return "32비트 정수", lambda v: isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi
    if isinstance(ty, Float):
        return "유한한 숫자", lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
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
            if t.name not in names:
                problems.append(f"대상에 테이블이 없습니다: {t.name}. 스키마가 head 와 다릅니다")
        # 모델 밖 테이블까지 본다. 빈 DB 에만 옮긴다
        for name in sorted(names - {"alembic_version"}):
            n = conn.execute(text(f'SELECT count(*) FROM "{name}"')).scalar()
            if n:
                problems.append(f"대상 {name} 에 이미 {n}행이 있습니다. 빈 DB 에만 옮깁니다")
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
    """execute_values 로 1,000행씩 묶어 넣는다. 행마다 왕복하면 원격 DB 에서 수십 분이 걸린다."""
    from psycopg2.extras import execute_values

    if not rows:
        return
    names = ", ".join(f'"{c.name}"' for c in cols)
    template = "(" + ", ".join("CAST(%s AS json)" if _is_json(c) else "%s" for c in cols) + ")"
    cur = conn.connection.cursor()  # 같은 트랜잭션의 DBAPI 연결
    try:
        execute_values(cur, f'INSERT INTO "{table.name}" ({names}) VALUES %s', rows,
                       template=template, page_size=1000)
    finally:
        cur.close()


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
    """다음 id 가 max(id)+1 이 되게 한다. 빈 테이블은 1 부터.

    ★setval 이 아니라 ALTER SEQUENCE RESTART 를 쓴다. setval 은 트랜잭션을 되돌려도 남아서
      dry-run 과 검증 실패 뒤에도 대상 시퀀스가 바뀐 채로 남는다(실측). RESTART 는 같이 되돌려진다.
    """
    from sqlalchemy import text

    for table in metadata().sorted_tables:
        if "id" not in table.columns:
            continue
        seq = conn.execute(text("SELECT pg_get_serial_sequence(:t, 'id')"), {"t": table.name}).scalar()
        if not seq:
            continue
        top = conn.execute(text(f'SELECT max(id) FROM "{table.name}"')).scalar()
        conn.execute(text(f"ALTER SEQUENCE {seq} RESTART WITH {int(top or 0) + 1}"))


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
    if data_type == "json":
        # json 타입은 넣은 텍스트를 그대로 보관한다. 원문과 글자까지 같아야 한다.
        # 파싱해 비교하면 true 와 1 이 같다고 나온다(파이썬에서 True == 1).
        return raw == got
    if data_type == "jsonb":
        return _strict_json(json.loads(raw)) == _strict_json(json.loads(got))
    if data_type in ("double precision", "real", "numeric"):
        return float(raw) == float(got)
    return str(raw) == got


def _strict_json(v):
    """불리언과 숫자를 구분해 비교할 수 있게 타입을 붙인다."""
    if isinstance(v, dict):
        return ("o", tuple(sorted((k, _strict_json(x)) for k, x in v.items())))
    if isinstance(v, list):
        return ("a", tuple(_strict_json(x) for x in v))
    return (type(v).__name__, v)


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
        nxt = last + 1 if called else last
        if nxt != (top or 0) + 1:
            problems.append(f"{table}: 시퀀스 다음 값이 {nxt} 입니다. {(top or 0) + 1} 이어야 합니다")
    return problems


# ── 첨부 ─────────────────────────────────────────────────────────────────────

ATTACHMENT_PREFIX = "attachments/"


@dataclass
class AttachmentReport:
    moved: list = field(default_factory=list)
    skipped_same: list = field(default_factory=list)
    #: uploads 에만 있고 DB 행이 없는 파일. 옮기지 않고 목록만 남긴다
    orphan_files: list = field(default_factory=list)


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


def migrate_attachments(conn, uploads_dir: str, storage) -> AttachmentReport:
    """DB 행이 있는 첨부를 attachments/<파일명> 키로 올리고 filepath 를 바꾼다.

    다시 실행해도 안전하다: 같은 키에 같은 해시가 있으면 건너뛴다. 다른 내용이 있으면 멈춘다.
    원본 파일은 지우지 않는다. Storage 업로드는 DB 트랜잭션 밖의 일이라 filepath 갱신만 트랜잭션에 든다.
    """
    from sqlalchemy import text

    from services.storage import StorageConflict, check_key

    rep = AttachmentReport()
    root = Path(uploads_dir)
    # .gitkeep 같은 숨김 파일은 첨부가 아니다
    # 로컬 저장소 루트가 uploads 와 같으면 이 함수가 만든 attachments/ 가 그 안에 생긴다. 그건 원본이 아니다
    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*")
               if p.is_file() and not p.name.startswith(".")} if root.is_dir() else set()
    on_disk = {f for f in on_disk if not f.startswith(ATTACHMENT_PREFIX)}
    referenced = set()
    rows = conn.execute(text("SELECT id, filepath, content_type FROM attachments ORDER BY id")).all()
    for att_id, filepath, content_type in rows:
        name = filepath[len(ATTACHMENT_PREFIX):] if filepath.startswith(ATTACHMENT_PREFIX) else filepath
        referenced.add(name)
        key = ATTACHMENT_PREFIX + name
        try:
            check_key(key)
        except ValueError:
            raise MigrationError([f"첨부 {att_id}: 저장소 키로 쓸 수 없는 파일 이름입니다: {name!r}"])
        local = root / name
        if not local.is_file():
            raise MigrationError([f"첨부 {att_id}: uploads 에 파일이 없습니다: {name}"])
        data = local.read_bytes()
        want = _sha(data)
        # ★있는지 먼저 묻지 않고 '없을 때만 쓰기'(put_new)로 올린다. size() 는 HEAD 400 이나
        #   Content-Length 없음도 None 이라, 그걸 '없음' 으로 읽고 덮어쓰면 남의 객체를 잃는다.
        try:
            storage.put_new(key, data, content_type)
            moved = True
        except StorageConflict:
            moved = False
        if _sha(storage.read(key, len(data) + 1)) != want:
            what = "올린 뒤 다시 읽은" if moved else "저장소에 이미 있는"
            raise MigrationError([f"첨부 {att_id}: {what} {key} 가 원본 {name} 과 내용이 다릅니다"])
        (rep.moved if moved else rep.skipped_same).append(att_id)
        if filepath != key:
            conn.execute(text("UPDATE attachments SET filepath = :k WHERE id = :i"), {"k": key, "i": att_id})
    rep.orphan_files = sorted(on_disk - referenced)
    return rep


# ── 실행 ─────────────────────────────────────────────────────────────────────

def _run_attachments(eng, uploads: str, after_data: bool = False) -> int:
    from services.storage import get_storage

    try:
        with eng.begin() as conn:
            rep = migrate_attachments(conn, uploads, get_storage())
    except Exception as e:  # 저장소 장애, 파일 I/O, 읽기 상한 초과까지. filepath 갱신은 되돌려진다
        problems = e.problems if isinstance(e, MigrationError) else [f"첨부 단계 오류: {type(e).__name__}: {e}"]
        if after_data:
            problems = ["데이터는 옮겼고 첨부 단계에서 멈췄습니다. 원인을 고친 뒤 "
                        "--attachments-only 로 다시 실행하세요"] + problems
        raise MigrationError(problems) from e
    print(f"첨부: 이동 {rep.moved}, 이미 있음 {rep.skipped_same}, DB 행 없는 파일(옮기지 않음) {rep.orphan_files}")
    return 0


def supabase_ref(url: str):
    """https://<ref>.supabase.co 의 ref. Supabase 주소가 아니면 None."""
    host = urllib.parse.urlparse(url or "").hostname or ""
    return host.split(".", 1)[0] if host.endswith(".supabase.co") else None


def target_matches_ref(target: str, ref: str) -> bool:
    """대상 DB 주소가 그 Supabase 프로젝트인가. 직결은 db.<ref>.supabase.co, 풀러는 사용자 postgres.<ref>."""
    from sqlalchemy.engine import make_url

    u = make_url(target)
    return u.host == f"db.{ref}.supabase.co" or (u.username or "").endswith("." + ref)


def _choose_storage(a) -> str:
    """첨부를 올릴 저장소를 정하고 설명을 돌려준다. 맞지 않으면 MigrationError."""
    if a.storage is None:
        raise MigrationError(["첨부가 있습니다. --storage local 또는 --storage supabase 로 올릴 저장소를 정하세요"])
    if a.storage == "supabase":
        ref = supabase_ref(os.environ.get("SUPABASE_URL", ""))
        if not ref:
            raise MigrationError(["--storage supabase 에는 SUPABASE_URL(https://<ref>.supabase.co)이 필요합니다"])
        if not target_matches_ref(a.target, ref):
            raise MigrationError([f"SUPABASE_URL 의 프로젝트({ref})가 --target 의 프로젝트와 다릅니다. "
                                  "다른 프로젝트의 버킷에 첨부를 올리지 않도록 멈췄습니다"])
        bucket = os.environ.get("STORAGE_BUCKET", "attachments")
        desc = f"supabase 프로젝트 {ref}, 버킷 {bucket}"
    else:
        root = os.environ.get("UPLOAD_DIR") or os.path.join(BACKEND, "uploads")
        desc = f"local {os.path.abspath(root)}"
    os.environ["STORAGE_BACKEND"] = a.storage
    return desc


def _parse_orphan(s: str) -> tuple[str, int]:
    table, _, rid = s.partition(":")
    if not table or not rid.isdigit():
        raise ValueError(f"--allow-orphan 형식은 테이블:id 입니다: {s}")
    return table, int(rid)


def main(argv=None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="SQLite(v1.10.3.1) -> PostgreSQL 데이터 이관")
    p.add_argument("--source", required=True, help="원본 SQLite 파일(읽기 전용으로 연다)")
    p.add_argument("--target", required=True, help="대상 PostgreSQL 주소. 직결 또는 세션 풀러")
    p.add_argument("--uploads", help="원본 첨부 폴더(backend/uploads). 첨부 행이 있으면 실제 실행에 필요")
    p.add_argument("--storage", choices=["local", "supabase"],
                   help="첨부를 올릴 저장소. 첨부가 있는 실제 실행에 필요. supabase 는 SUPABASE_URL 등 환경변수를 쓴다")
    p.add_argument("--allow-orphan", action="append", default=[], metavar="TABLE:ID",
                   help="FK 고아 행을 옮기지 않고 제외한다. 여러 번 줄 수 있다")
    p.add_argument("--excluded-out", default="excluded_rows.json", help="제외한 행을 보관할 JSON")
    p.add_argument("--dry-run", action="store_true", help="점검·복사·검증 후 되돌린다. 첨부는 건드리지 않는다")
    p.add_argument("--attachments-only", action="store_true",
                   help="데이터는 이미 옮겼고 첨부 단계만 다시 돈다(첨부 단계가 실패했을 때)")
    a = p.parse_args(argv)

    os.environ["DATABASE_URL"] = a.target  # 모델 임포트용
    os.environ["DATABASE_URL_DIRECT"] = ""
    import psycopg2
    from sqlalchemy import create_engine
    from sqlalchemy.exc import DBAPIError
    from sqlalchemy.pool import NullPool

    try:
        allow = {_parse_orphan(s) for s in a.allow_orphan}
        src = open_source(a.source)
        eng = create_engine(a.target, poolclass=NullPool)
        if a.attachments_only:
            if a.dry_run:
                raise MigrationError(["--attachments-only 와 --dry-run 은 같이 쓸 수 없습니다. "
                                      "첨부 단계는 저장소에 바로 올립니다"])
            if not a.uploads:
                raise MigrationError(["--attachments-only 에는 --uploads 가 필요합니다"])
            print(f"첨부 저장소: {_choose_storage(a)}")
            return _run_attachments(eng, a.uploads)
        pre = precheck(src, eng, allow)
        n_att = src.execute("SELECT count(*) FROM attachments").fetchone()[0]
        if n_att and not a.dry_run:
            if not a.uploads:
                raise MigrationError([f"첨부 {n_att}건이 있습니다. --uploads 로 원본 첨부 폴더를 주세요"])
            # 데이터를 쓰기 전에 저장소부터 정한다. 커밋 뒤에 멈추면 복구가 번거롭다
            print(f"첨부 저장소: {_choose_storage(a)}")
        Path(a.excluded_out).write_text(json.dumps(pre.excluded_rows, ensure_ascii=False, indent=1, default=str),
                                        encoding="utf-8")
        with eng.connect() as conn:
            trans = conn.begin()
            counts = copy_all(src, conn, pre.excluded)
            fix_sequences(conn)
            problems = verify(src, conn, pre.excluded)
            if problems:
                trans.rollback()
                raise MigrationError(["검증 실패. 아무것도 남기지 않았습니다"] + problems)
            if a.dry_run:
                trans.rollback()
            else:
                trans.commit()
        for t, n in counts.items():
            print(f"  {t}: {n}")
        excluded = {t: sorted(ids) for t, ids in pre.excluded.items()}
        print(f"제외: {excluded} -> {a.excluded_out}")
        if a.dry_run:
            print("dry-run: 점검, 복사, 검증 통과. 되돌렸습니다")
            return 0
        print("데이터 이관 완료(검증 통과)")
        if n_att:
            return _run_attachments(eng, a.uploads, after_data=True)
        return 0
    except (MigrationError, ValueError, DBAPIError, psycopg2.Error) as e:
        if isinstance(e, MigrationError):
            problems = e.problems
        elif isinstance(e, (DBAPIError, psycopg2.Error)):
            first = str(getattr(e, "orig", e)).strip().splitlines()
            problems = ["대상 DB 가 거부했습니다. 아무것도 남기지 않았습니다(트랜잭션 되돌림)"] + [x.strip() for x in first[:3]]
        else:
            problems = [str(e)]
        print("이관을 멈췄습니다:", file=sys.stderr)
        for line in problems:
            print("  - " + line, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
