"""DB 의 Alembic 리비전이 이 코드가 아는 것인지 본다.

v2.0 에서 SQLite 시절 이력 14개를 PostgreSQL 기준점 하나로 압축했다. 옛 이력으로
만든 DB 는 이 코드의 어떤 리비전과도 이어지지 않는다. alembic 이 내는
"Can't locate revision" 은 이유를 말해 주지 않으므로 여기서 먼저 알린다.

★옛 이력이 아닌 모르는 리비전은 막지 않는다. 롤백(이전 배포 승격)은 새 스키마 위에서
  옛 코드를 띄우는데, 그때 기동을 막으면 롤백 자체가 안 된다. 스키마 변경은 추가 먼저,
  삭제는 다음 릴리즈 원칙이라 옛 코드가 새 스키마에서 돈다.
"""
import logging

from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

#: sqlite-legacy 브랜치(v1.10.3.1)의 리비전 id. 이 값이면 옛 SQLite 이력이다.
LEGACY_SQLITE_REVISIONS = frozenset({
    "8925bb1ad2db", "05f8800a57f5", "06933fddb519", "5e0b8c2d4f17", "a1c4e7b9d2f0",
    "a3d61f0c8be2", "a7d3e5c19f42", "b7c31d9e42f8", "b7d3c9a1e450", "c2f8a90b3d14",
    "c9e2f4a17b03", "d41b6c8e5a27", "e5a83f21c760", "f2b7c04e91a8",
})


def assert_known_revision(conn, script_dir: ScriptDirectory) -> None:
    if "alembic_version" not in inspect(conn).get_table_names():
        return
    known = {rev.revision for rev in script_dir.walk_revisions()}
    current = [r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))]
    legacy = [r for r in current if r in LEGACY_SQLITE_REVISIONS]
    if legacy:
        raise RuntimeError(
            f"이 DB 의 리비전 {legacy} 은 SQLite 시절 이력이다. "
            "v2.0 은 새 DB 에 기준점부터 올린다. 기존 데이터는 "
            "scripts/migrate_sqlite_to_pg.py 로 옮기고, SQLite 로 계속 쓰려면 "
            "sqlite-legacy 브랜치를 쓴다."
        )
    newer = [r for r in current if r not in known]
    if newer:
        logger.warning("DB 스키마 리비전 %s 를 이 코드가 모른다. 코드보다 새 스키마(롤백 상태)로 본다.", newer)


def schema_status(conn, script_dir: ScriptDirectory) -> str:
    """DB 스키마와 코드의 관계. empty / current / behind / ahead.

    ahead 는 코드가 모르는 더 새 리비전(롤백 상태)이다. 막지 않는다.
    """
    if "alembic_version" not in inspect(conn).get_table_names():
        return "empty"
    current = {r[0] for r in conn.execute(text("SELECT version_num FROM alembic_version"))}
    if not current:
        return "empty"
    known = {rev.revision for rev in script_dir.walk_revisions()}
    if current - known:
        return "ahead"
    heads = set(script_dir.get_heads())
    return "current" if current == heads else "behind"
