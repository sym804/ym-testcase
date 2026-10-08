"""DB 의 Alembic 리비전이 이 코드가 아는 것인지 본다.

v2.0 에서 SQLite 시절 이력 14개를 PostgreSQL 기준점 하나로 압축했다. 옛 이력으로
만든 DB 는 이 코드의 어떤 리비전과도 이어지지 않는다. alembic 이 내는
"Can't locate revision" 은 이유를 말해 주지 않으므로 여기서 먼저 알린다.
"""
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text


def assert_known_revision(conn, script_dir: ScriptDirectory) -> None:
    if "alembic_version" not in inspect(conn).get_table_names():
        return
    known = {rev.revision for rev in script_dir.walk_revisions()}
    current = [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]
    unknown = [r for r in current if r not in known]
    if unknown:
        raise RuntimeError(
            f"이 DB 의 리비전 {unknown} 은 SQLite 시절 이력이다. "
            "v2.0 은 새 DB 에 기준점부터 올린다. 기존 데이터는 "
            "scripts/migrate_sqlite_to_pg.py 로 옮기고, SQLite 로 계속 쓰려면 "
            "sqlite-legacy 브랜치를 쓴다."
        )
