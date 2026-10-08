# 계획 1: PostgreSQL 단일화 기반 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 로컬 개발, 테스트, CI 가 전부 PostgreSQL 로 돌고, SQLite 전용 코드가 없는 상태를 만든다.

**Architecture:** Docker 의 PostgreSQL 을 로컬 DB 로 쓴다. Alembic 이력은 PostgreSQL 기준점 하나로 압축한다. 테스트는 서버 테스트가 세션마다 임시 데이터베이스를, 단위 테스트가 테스트마다 임시 스키마를 쓴다. 공용 헬퍼 `backend/testing_db.py` 하나가 접속을 만들고 원격 주소를 거부한다.

**Tech Stack:** PostgreSQL(Supabase 와 같은 메이저, 아래 Task 1 에서 고정), psycopg2-binary 2.9.11, SQLAlchemy 2.0.48, Alembic, pytest 9.1.1, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md`

이 계획은 스펙의 세 계획 중 첫 번째다.

1. (이 문서) PostgreSQL 기반: 로컬 DB, DB 계층, 기준점, 테스트 하네스, SQLite 전용 코드, CI
2. 동시성 계약, 공유 상태, Storage 직접 업로드, 스키마 버전 503, Cron, RLS, Vercel 배치와 워크플로
3. 데이터 이관 스크립트, 문서, 버전, `sqlite-legacy` 브랜치

## Global Constraints

- 작업 위치: worktree `C:\Users\ymseo\Documents\tc_manager-pg`, 브랜치 `feat/postgresql`. 원본 폴더와 `main` 은 건드리지 않는다(컷오버 전까지 사용자의 로컬 SQLite 사용을 유지).
- 로컬 PostgreSQL 포트 `54329`, 테스트 서버 포트 `TEST_PORT=8018`. 사용자의 8008/5173 과 겹치지 않는다.
- 테스트 DB 주소의 호스트는 `127.0.0.1`, `localhost`, `::1` 만 허용한다.
- `DATABASE_URL` 이 없으면 기동 단계에서 예외. SQLite 기본값을 어디에도 두지 않는다.
- 엠대시(U+2014), 엔대시(U+2013) 금지. 사용자 대상 서술은 한글.
- 커밋은 작업 단위로. 이 브랜치의 커밋은 릴리즈 노트·이슈 로그 갱신 없이 쌓고, `main` 머지 시점(계획 3)에 System 2.0.0.0 릴리즈로 묶는다.
- 런타임 동작이 바뀌는 커밋 묶음은 머지 전 QA 2인(Codex `-s read-only` + 자체 리뷰 에이전트) 검증.

## Review Focus

- 개발자가 `.env` 에 운영 Supabase 주소를 넣은 채 pytest 를 돌리는 경우: 테스트가 그 DB 에 쓰지 않고 즉시 실패해야 한다. Task 1, Task 4 의 가드 테스트가 고정한다.
- 이미 8018 에 서버가 떠 있는 상태에서 pytest: 기존 `dev_db_guard` 건너뛰기가 그대로 동작해야 한다. Task 4 에서 회귀 테스트로 고정한다.
- 시트 안에 소프트 삭제된 TC 가 섞인 상태의 재번호: 살아 있는 TC 가 1..N 이 되고 유니크 충돌이 없어야 한다. Task 6 테스트가 고정한다.
- 고급 필터에서 정수 칸 `no` 에 "포함", "빈 값", 숫자가 아닌 값: 500 이 아니라 400. Task 7 테스트가 고정한다.
- Docker 가 꺼진 상태에서 `devctl up`: 무엇을 켜야 하는지 알려 주고 멈춰야 한다. Task 9 에서 고정한다.

---

### Task 1: 로컬 PostgreSQL 과 테스트 DB 헬퍼

**Files:**
- Create: `docker-compose.yml` (레포 루트)
- Modify: `.gitignore` (`docker-compose.yml` 줄 제거)
- Create: `backend/testing_db.py`
- Test: `backend/tests_unit/test_testing_db.py`

**Interfaces:**
- Produces:
  - `testing_db.admin_url() -> str`: `TEST_DATABASE_ADMIN_URL` 또는 기본값. 로컬 호스트가 아니면 `RuntimeError`
  - `testing_db.create_database(prefix: str = "ymtc_test") -> str`: 새 DB 를 만들고 그 접속 주소를 돌려준다
  - `testing_db.drop_database(url: str) -> None`
  - `testing_db.schema_engine(base_url: str) -> sqlalchemy.Engine`: 임시 스키마를 만들고 `search_path` 를 거기로 둔 엔진, `Base.metadata.create_all` 까지 한다
  - `testing_db.dispose_schema_engine(engine) -> None`: 스키마를 지우고 엔진을 닫는다

- [ ] **Step 1: PostgreSQL 메이저 버전 확인**

Supabase 공식 문서에서 신규 프로젝트의 PostgreSQL 메이저 버전을 확인한다. 17 이면 아래 이미지 태그를 그대로 쓰고, 다르면 태그를 그 값으로 바꾼다.

- [ ] **Step 2: docker-compose.yml 작성**

```yaml
# 로컬 개발과 테스트용 PostgreSQL. 운영은 Supabase 이고 이 파일과 무관하다.
# 메이저 버전은 Supabase 와 맞춘다(docs/superpowers/specs/2026-10-08-postgresql-vercel-supabase-design.md).
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_USER: ymtc
      POSTGRES_PASSWORD: ymtc
      POSTGRES_DB: ymtc
    ports:
      - "127.0.0.1:54329:5432"
    volumes:
      - ymtc-pg:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ymtc -d ymtc"]
      interval: 2s
      timeout: 3s
      retries: 30

volumes:
  ymtc-pg:
```

`.gitignore` 에서 `docker-compose.yml` 줄을 지운다.

Run: `docker compose up -d db && docker compose ps`
Expected: `db` 가 `healthy`

- [ ] **Step 3: 실패하는 테스트 작성**

```python
"""테스트 DB 헬퍼

테스트가 원격 DB(특히 Supabase 운영)에 쓰는 일을 막는 것이 이 헬퍼의 첫째 일이다.
"""
import os
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db
from sqlalchemy import inspect, text


def test_원격_호스트는_거부한다(monkeypatch):
    monkeypatch.setenv(
        "TEST_DATABASE_ADMIN_URL",
        "postgresql+psycopg2://u:p@db.example.supabase.co:5432/postgres",
    )
    with pytest.raises(RuntimeError, match="로컬"):
        testing_db.admin_url()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_로컬_호스트는_허용한다(monkeypatch, host):
    monkeypatch.setenv("TEST_DATABASE_ADMIN_URL", f"postgresql+psycopg2://u:p@{host}:54329/postgres")
    assert host in testing_db.admin_url()


def test_임시_DB_를_만들고_지운다():
    url = testing_db.create_database(prefix="ymtc_selftest")
    try:
        from sqlalchemy import create_engine
        eng = create_engine(url)
        with eng.connect() as c:
            assert c.execute(text("select 1")).scalar() == 1
        eng.dispose()
    finally:
        testing_db.drop_database(url)
    from sqlalchemy import create_engine
    admin = create_engine(testing_db.admin_url(), isolation_level="AUTOCOMMIT")
    name = url.rsplit("/", 1)[1]
    with admin.connect() as c:
        left = c.execute(text("select 1 from pg_database where datname=:n"), {"n": name}).first()
    admin.dispose()
    assert left is None


def test_스키마_엔진은_서로_격리된다():
    base = testing_db.create_database(prefix="ymtc_selftest")
    try:
        a = testing_db.schema_engine(base)
        b = testing_db.schema_engine(base)
        try:
            with a.begin() as c:
                c.execute(text("insert into users (username, password_hash, display_name, role, must_change_password, token_version) values ('x','h','x','user',false,0)"))
            with b.connect() as c:
                assert c.execute(text("select count(*) from users")).scalar() == 0
            assert "users" in inspect(a).get_table_names()
        finally:
            testing_db.dispose_schema_engine(a)
            testing_db.dispose_schema_engine(b)
    finally:
        testing_db.drop_database(base)
```

- [ ] **Step 4: 실패 확인**

Run: `cd backend && python -m pytest tests_unit/test_testing_db.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'testing_db'`

- [ ] **Step 5: 구현**

`backend/testing_db.py`:

```python
"""테스트용 PostgreSQL 접속을 한 곳에서 만든다.

서버 테스트는 세션마다 임시 데이터베이스를, 단위 테스트는 테스트마다 임시 스키마를
쓴다. 둘 다 이 모듈을 거친다.

★관리 주소의 호스트가 로컬이 아니면 거부한다. `.env` 에 운영 Supabase 주소가 들어
  있는 채로 pytest 를 돌려도 테스트가 그 DB 를 만지지 못하게 하는 것이 이 모듈의
  첫째 일이다. SQLite 시절의 `/tc_manager.db` 접미사 판정을 대신한다.
"""
import os
import uuid

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url

DEFAULT_ADMIN_URL = "postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc"
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def admin_url() -> str:
    url = os.getenv("TEST_DATABASE_ADMIN_URL", DEFAULT_ADMIN_URL)
    host = make_url(url).host
    if host not in _LOCAL_HOSTS:
        raise RuntimeError(f"테스트 DB 는 로컬 호스트만 허용한다: {host}")
    return url


def _admin_engine() -> Engine:
    return create_engine(admin_url(), isolation_level="AUTOCOMMIT")


def create_database(prefix: str = "ymtc_test") -> str:
    name = f"{prefix}_{uuid.uuid4().hex[:10]}"
    eng = _admin_engine()
    try:
        with eng.connect() as c:
            c.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        eng.dispose()
    return make_url(admin_url()).set(database=name).render_as_string(hide_password=False)


def drop_database(url: str) -> None:
    name = make_url(url).database
    eng = _admin_engine()
    try:
        with eng.connect() as c:
            c.execute(
                text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                     "WHERE datname = :n AND pid <> pg_backend_pid()"),
                {"n": name},
            )
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        eng.dispose()


def schema_engine(base_url: str) -> Engine:
    """임시 스키마 하나를 만들고 그 안에 현재 모델의 테이블을 만든 엔진.

    enum 타입도 `search_path` 의 첫 스키마에 생기므로 테스트끼리 섞이지 않는다.
    """
    import models  # noqa: F401  Base 에 테이블을 등록한다
    from database import Base

    schema = f"t_{uuid.uuid4().hex[:12]}"
    boot = create_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        with boot.connect() as c:
            c.execute(text(f'CREATE SCHEMA "{schema}"'))
    finally:
        boot.dispose()
    eng = create_engine(base_url, connect_args={"options": f"-csearch_path={schema}"})
    eng.info["ymtc_schema"] = schema
    Base.metadata.create_all(eng)
    return eng


def dispose_schema_engine(engine: Engine) -> None:
    schema = engine.info["ymtc_schema"]
    url = engine.url
    engine.dispose()
    boot = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with boot.connect() as c:
            c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
    finally:
        boot.dispose()
```

`Engine.info` 가 없는 SQLAlchemy 버전이면 `eng._ymtc_schema = schema` 속성으로 바꾸고 두 함수에서 같은 이름을 쓴다.

- [ ] **Step 6: 통과 확인**

Run: `cd backend && python -m pytest tests_unit/test_testing_db.py -q`
Expected: `5 passed`

- [ ] **Step 7: 커밋**

```bash
git add docker-compose.yml .gitignore backend/testing_db.py backend/tests_unit/test_testing_db.py
git commit -m "test: 로컬 PostgreSQL 과 테스트 DB 헬퍼 (SYM-6)"
```

---

### Task 2: DB 계층에서 SQLite 제거

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/alembic/env.py`
- Modify: `backend/alembic.ini:89`
- Modify: `backend/main.py:40-66`
- Create: `backend/services/schema_version.py`
- Delete: `backend/services/schema_guard.py`
- Modify: `backend/.env.example`, 루트 `.env.example`
- Test: `backend/tests_unit/test_db_config.py`, `backend/tests_unit/test_schema_version.py`

**Interfaces:**
- Consumes: `testing_db.create_database`, `testing_db.drop_database` (Task 1)
- Produces:
  - `database.require_database_url() -> str`: 없거나 `sqlite` 면 `RuntimeError`
  - `services.schema_version.assert_known_revision(conn, script_dir) -> None`: `alembic_version` 의 값이 스크립트 디렉터리에 없으면 `sqlite-legacy` 안내와 함께 `RuntimeError`
  - 환경변수 `RUN_MIGRATIONS_ON_STARTUP` (기본 `"1"`), `DB_POOL` (`"null"` 이면 `NullPool`)

- [ ] **Step 1: 실패하는 테스트 작성**

`backend/tests_unit/test_db_config.py`:

```python
"""DB 주소는 반드시 명시한다. 조용히 SQLite 로 떨어지면 배포가 엉뚱한 파일에 성공한다."""
import os
import subprocess
import sys

import pytest

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _import_database(env_overrides: dict) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "DATABASE_URL"}
    env.update(env_overrides)
    env["ENV_FILE"] = os.path.join(BACKEND, "does-not-exist.env")
    return subprocess.run(
        [sys.executable, "-c", "import database"],
        cwd=BACKEND, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def test_DATABASE_URL_이_없으면_임포트에서_실패한다():
    r = _import_database({})
    assert r.returncode != 0
    assert "DATABASE_URL" in r.stderr


def test_sqlite_주소는_거부한다():
    r = _import_database({"DATABASE_URL": "sqlite:///./x.db"})
    assert r.returncode != 0
    assert "PostgreSQL" in r.stderr


def test_postgresql_주소면_임포트된다():
    r = _import_database({"DATABASE_URL": "postgresql+psycopg2://u:p@127.0.0.1:1/x"})
    assert r.returncode == 0, r.stderr


def test_alembic_ini_에_기본_주소가_없다():
    ini = open(os.path.join(BACKEND, "alembic.ini"), encoding="utf-8").read()
    assert "sqlite" not in ini
```

`backend/tests_unit/test_schema_version.py`:

```python
"""모르는 리비전을 만나면 sqlite-legacy 이력이라고 알리고 멈춘다."""
import os
import sys

import pytest
from alembic.script import ScriptDirectory
from alembic.config import Config
from sqlalchemy import create_engine, text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db
from services.schema_version import assert_known_revision


def _script_dir():
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    return ScriptDirectory.from_config(cfg)


@pytest.fixture
def conn():
    url = testing_db.create_database(prefix="ymtc_sv")
    eng = create_engine(url)
    with eng.connect() as c:
        yield c
    eng.dispose()
    testing_db.drop_database(url)


def test_빈_DB_는_통과한다(conn):
    assert_known_revision(conn, _script_dir())


def test_옛_SQLite_이력의_리비전이면_안내하고_멈춘다(conn):
    conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) primary key)"))
    conn.execute(text("INSERT INTO alembic_version VALUES ('5e0b8c2d4f17')"))
    with pytest.raises(RuntimeError, match="sqlite-legacy"):
        assert_known_revision(conn, _script_dir())


def test_현재_head_면_통과한다(conn):
    head = _script_dir().get_current_head()
    conn.execute(text("CREATE TABLE alembic_version (version_num varchar(32) primary key)"))
    conn.execute(text("INSERT INTO alembic_version VALUES (:h)"), {"h": head})
    assert_known_revision(conn, _script_dir())
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests_unit/test_db_config.py tests_unit/test_schema_version.py -q`
Expected: `test_DATABASE_URL_이_없으면...`, `test_sqlite_주소는_거부한다`, `test_alembic_ini...` FAIL, `test_schema_version.py` 는 `ModuleNotFoundError`

`test_옛_SQLite_이력...` 은 Task 3 의 기준점 압축 전까지 `5e0b8c2d4f17` 이 스크립트 디렉터리에 있어 실패가 정상이다. Task 3 뒤에 통과한다.

- [ ] **Step 3: database.py 구현**

```python
# .env 로딩 - 아래 os.getenv 호출보다 먼저 실행되어야 한다
import env_setup  # noqa: F401

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import NullPool


def require_database_url() -> str:
    """DATABASE_URL 을 읽는다. 없거나 SQLite 면 멈춘다.

    ★기본값을 두지 않는다. 기본값이 있으면 주소 전달이 빠진 배포가 로컬 파일 DB 에
      조용히 성공한다. 실패가 늦게 드러나는 것보다 지금 멈추는 편이 싸다.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL 이 설정되지 않았다. backend/.env.example 참고")
    if url.startswith("sqlite"):
        raise RuntimeError(
            "SQLite 는 더 지원하지 않는다. PostgreSQL 주소를 쓴다. "
            "SQLite 버전은 sqlite-legacy 브랜치(v1.10.3.1)"
        )
    return url


DATABASE_URL = require_database_url()

_engine_kwargs = {"pool_pre_ping": True}
# 서버리스는 실행 환경이 수시로 생기고 사라져 풀을 들고 있을 이유가 없다.
# 연결 재사용은 Supabase 풀러가 맡는다.
if os.getenv("DB_POOL") == "null":
    _engine_kwargs["poolclass"] = NullPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: schema_version.py 구현**

```python
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
```

- [ ] **Step 5: alembic env.py, alembic.ini, main.py 수정**

`alembic.ini:89` 의 `sqlalchemy.url = sqlite:///./tc_manager.db` 를 `sqlalchemy.url =` 로 비운다.

`alembic/env.py` 의 URL 결정부와 configure 를 바꾼다.

```python
# 마이그레이션은 트랜잭션 풀러를 피해 직결(또는 세션 풀러) 주소로 한다.
# 둘 다 없으면 멈춘다. 빈 값으로 진행하면 엉뚱한 곳에 "성공" 할 수 있다.
db_url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL_DIRECT 또는 DATABASE_URL 이 필요하다")
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
```

`run_migrations_offline` 과 `run_migrations_online` 의 `render_as_batch=True` 두 줄을 지운다(SQLite 전용).

`main.py` lifespan 을 바꾼다.

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    from alembic.config import Config as AlembicConfig
    from alembic import command as alembic_command
    from alembic.script import ScriptDirectory
    from database import engine, DATABASE_URL
    from services.schema_version import assert_known_revision

    alembic_cfg = AlembicConfig(os.path.join(os.path.dirname(__file__), "alembic.ini"))
    alembic_cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "alembic"))

    with engine.connect() as conn:
        assert_known_revision(conn, ScriptDirectory.from_config(alembic_cfg))

    # 서버리스에서는 끈다. 실행 환경마다 동시에 돌기 때문이다. 배포 워크플로가 대신 한다.
    if os.getenv("RUN_MIGRATIONS_ON_STARTUP", "1") == "1":
        alembic_command.upgrade(alembic_cfg, "head")

    _purge_old_deleted_testcases()
    yield
```

`from services.schema_guard import ...` 와 pre-Alembic stamp 분기를 지우고 `services/schema_guard.py` 를 삭제한다. `main.py:47` 의 `db_url = os.getenv("DATABASE_URL", "sqlite:///./tc_manager.db")` 줄도 지운다(env.py 가 환경변수를 직접 읽는다).

`alembic.ini` 의 `script_location` 값이 상대경로라 서버를 다른 작업 폴더에서 띄우면 못 찾는다. 위처럼 절대경로로 덮는다.

- [ ] **Step 6: .env.example 수정**

`backend/.env.example` 와 루트 `.env.example` 의 DB 줄을 바꾼다.

```
# 데이터베이스 URL (PostgreSQL 필수. 로컬은 docker compose up -d db)
DATABASE_URL=postgresql+psycopg2://ymtc:ymtc@127.0.0.1:54329/ymtc

# 마이그레이션 전용 주소 (배포: Supabase 직결 또는 세션 풀러). 비우면 DATABASE_URL
DATABASE_URL_DIRECT=

# 기동 시 alembic upgrade head (서버리스는 0)
RUN_MIGRATIONS_ON_STARTUP=1

# null 이면 연결 풀 없이 (서버리스)
DB_POOL=
```

- [ ] **Step 7: 통과 확인**

Run: `cd backend && python -m pytest tests_unit/test_db_config.py -q`
Expected: `4 passed`

- [ ] **Step 8: 커밋**

```bash
git add -A backend/database.py backend/alembic/env.py backend/alembic.ini backend/main.py backend/services/schema_version.py backend/services/schema_guard.py backend/.env.example .env.example backend/tests_unit/test_db_config.py backend/tests_unit/test_schema_version.py
git commit -m "refactor: DB 계층에서 SQLite 제거, DATABASE_URL 필수 (SYM-6)"
```

---

### Task 3: Alembic 기준점 압축

**Files:**
- Delete: `backend/alembic/versions/*.py` 14개
- Create: `backend/alembic/versions/0001_postgresql_baseline.py`
- Test: `backend/tests_unit/test_baseline_schema.py`

**Interfaces:**
- Consumes: `testing_db.create_database`, `testing_db.drop_database`
- Produces: 리비전 id `0001_pg_baseline` (head)

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""기준점 마이그레이션으로 만든 스키마가 현재 모델과 같다.

옛 이력과 비교하지 않는다. 운영 SQLite 는 Alembic 이전에 만들어져 stamp 된 DB 라
옛 이력의 결과와도 다르다. 비교 대상은 모델(Base.metadata) 하나다.
"""
import os
import subprocess
import sys

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

import testing_db


@pytest.fixture(scope="module")
def migrated_url():
    url = testing_db.create_database(prefix="ymtc_baseline")
    env = dict(os.environ, DATABASE_URL=url, DATABASE_URL_DIRECT="")
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND,
                       env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    yield url
    testing_db.drop_database(url)


def test_리비전은_하나다():
    versions = os.path.join(BACKEND, "alembic", "versions")
    files = [f for f in os.listdir(versions) if f.endswith(".py")]
    assert files == ["0001_postgresql_baseline.py"]


def test_모델과_차이가_없다(migrated_url):
    import models  # noqa: F401
    from database import Base

    eng = create_engine(migrated_url)
    with eng.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    eng.dispose()
    assert diff == []


def test_부분_유니크_인덱스_조건이_살아_있다(migrated_url):
    eng = create_engine(migrated_url)
    with eng.connect() as conn:
        rows = dict(conn.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes "
            "WHERE indexname IN ('uq_test_cases_project_tc_id', 'uq_test_cases_sheet_no')"
        )).all())
    eng.dispose()
    assert set(rows) == {"uq_test_cases_project_tc_id", "uq_test_cases_sheet_no"}
    for name, ddl in rows.items():
        assert "UNIQUE" in ddl and "deleted_at IS NULL" in ddl, (name, ddl)


def test_FK_삭제_동작이_모델과_같다(migrated_url):
    import models

    eng = create_engine(migrated_url)
    insp = inspect(eng)
    for table in models.Base.metadata.sorted_tables:
        db_fks = {(tuple(fk["constrained_columns"]), fk["referred_table"]): (fk.get("options") or {}).get("ondelete")
                  for fk in insp.get_foreign_keys(table.name)}
        for fk in table.foreign_keys:
            key = ((fk.parent.name,), fk.column.table.name)
            want = fk.ondelete.upper() if fk.ondelete else None
            got = db_fks[key].upper() if db_fks.get(key) else None
            assert got == want, (table.name, key, got, want)
    eng.dispose()
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && python -m pytest tests_unit/test_baseline_schema.py -q`
Expected: `test_리비전은_하나다` FAIL (파일 14개). 다른 테스트는 옛 이력이 PostgreSQL 에서 실패해 fixture 단계에서 ERROR 가 나거나 차이가 나온다. 어느 쪽이든 FAIL/ERROR 다.

- [ ] **Step 3: 옛 이력 삭제 후 기준점 생성**

```bash
cd backend
git rm -q alembic/versions/*.py
export DATABASE_URL=$(python -c "import testing_db; print(testing_db.create_database(prefix='ymtc_autogen'))")
python -m alembic revision --autogenerate --rev-id 0001_pg_baseline -m "postgresql baseline"
mv alembic/versions/0001_pg_baseline_postgresql_baseline.py alembic/versions/0001_postgresql_baseline.py
python -c "import testing_db,os; testing_db.drop_database(os.environ['DATABASE_URL'])"
```

생성된 파일을 열어 아래를 확인하고 고친다.

- 맨 위 docstring 을 이렇게 바꾼다: `"""PostgreSQL 기준점. SQLite 시절 이력 14개(마지막 5e0b8c2d4f17)를 압축했다. 옛 이력은 sqlite-legacy 브랜치에 있다."""`
- `down_revision = None`
- 부분 인덱스 두 개에 `postgresql_where=sa.text('deleted_at IS NULL')` 가 들어 있는지 본다. 빠졌으면 모델(`models.py:166`, `:175`)과 같게 넣는다.
- enum 타입 이름(`userrole`, `projectrole`, `testrunstatus`, `testresultvalue`, `accountrequesttype`, `accountrequeststatus` 등)이 `sa.Enum(..., name=...)` 으로 들어 있는지 본다.
- `downgrade()` 는 테이블 drop 뒤 enum 타입도 `sa.Enum(name=...).drop(op.get_bind(), checkfirst=True)` 로 지운다.

- [ ] **Step 4: 통과 확인**

Run: `cd backend && python -m pytest tests_unit/test_baseline_schema.py tests_unit/test_schema_version.py -q`
Expected: 전부 PASS. `compare_metadata` 가 차이를 내면 기준점 파일을 모델에 맞게 고친다. 모델을 고치지 않는다.

- [ ] **Step 5: 커밋**

```bash
git add -A backend/alembic/versions backend/tests_unit/test_baseline_schema.py
git commit -m "refactor: Alembic 이력을 PostgreSQL 기준점 하나로 압축 (SYM-6)"
```

---

### Task 4: 서버 테스트 하네스를 PostgreSQL 로

**Files:**
- Modify: `backend/conftest.py`
- Modify: `backend/test_db_isolation.py`
- Modify: `backend/dev_db_guard.py:30` (`DEFAULT_REQUEST_PORT` 주석만, 값 유지)

**Interfaces:**
- Consumes: `testing_db.create_database`, `testing_db.drop_database`, `testing_db.schema_engine`, `testing_db.dispose_schema_engine`
- Produces:
  - pytest fixture `pg_engine` (function scope): 임시 스키마 엔진. 모든 테스트에서 쓸 수 있다
  - pytest fixture `pg_session` (function scope): `pg_engine` 에 묶인 `Session`
  - `conftest.SESSION_DATABASE_URL`: 서버 테스트용 세션 DB 주소

- [ ] **Step 1: test_db_isolation.py 를 새 규칙으로 다시 쓴다 (실패하는 테스트)**

파일 전체를 아래로 바꾼다. 옛 테스트 중 `test_non_dev_database_url_is_respected` 는 "원격 주소를 그대로 쓴다" 를 정상으로 고정하고 있어 반대 단언으로 바뀐다.

```python
"""pytest 는 어떤 경우에도 세션 전용 임시 PostgreSQL DB 를 쓴다.

SQLite 시절에는 주소가 `/tc_manager.db` 로 끝날 때만 격리했다. PostgreSQL 주소는
그 판정에 안 걸려 그대로 쓰였고, `.env` 에 운영 주소가 있으면 테스트가 거기 썼다.
"""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.abspath(__file__))


def test_세션_DB_는_임시_DB_다():
    import conftest
    from sqlalchemy.engine import make_url

    if conftest.USING_RUNNING_DEV_SERVER:
        import pytest
        pytest.skip("이미 떠 있는 서버를 쓰는 모드")
    name = make_url(os.environ["DATABASE_URL"]).database
    assert name.startswith("ymtc_test_"), name


def test_앱_엔진도_같은_임시_DB_를_본다():
    import conftest
    from database import engine

    if conftest.USING_RUNNING_DEV_SERVER:
        import pytest
        pytest.skip("이미 떠 있는 서버를 쓰는 모드")
    assert engine.url.database == conftest.SESSION_DATABASE_NAME


def test_셸의_원격_DATABASE_URL_은_무시하고_임시_DB_를_쓴다():
    """셸에 운영 Supabase 주소가 있어도 pytest 는 그 주소를 쓰지 않는다."""
    code = (
        "import conftest, os;"
        "from sqlalchemy.engine import make_url;"
        "print(make_url(os.environ['DATABASE_URL']).host, make_url(os.environ['DATABASE_URL']).database)"
    )
    env = dict(os.environ,
               DATABASE_URL="postgresql+psycopg2://u:p@db.example.supabase.co:5432/postgres",
               TEST_PORT="18999")
    r = subprocess.run([sys.executable, "-c", code], cwd=BACKEND, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr
    host, db = r.stdout.split()
    assert host in ("127.0.0.1", "localhost"), host
    assert db.startswith("ymtc_test_"), db
```

- [ ] **Step 2: 실패 확인**

Run: `cd backend && TEST_PORT=8018 python -m pytest test_db_isolation.py -q`
Expected: FAIL. 지금 conftest 는 PostgreSQL 주소를 격리하지 않고 `SESSION_DATABASE_NAME` 도 없다.

- [ ] **Step 3: conftest.py 의 DB 격리부 교체**

`DEV_DB_SUFFIX`, `_needs_temp_db`, `_isolate_database_url`, `TEST_DB_DIR` 를 지우고 아래로 바꾼다. 나머지(타임아웃 패치, `_server_already_running`, `_request_port`, `dev_db_guard` 판정, `_wait_for_server`, `_seed_admin`, `_server`)는 그대로 둔다.

```python
import testing_db

#: 개발 서버가 이미 떠 있으면 HTTP 는 그 서버의 DB 로 간다. 그때 in-process engine 만
#: 임시 DB 로 돌리면 한 테스트가 두 DB 를 보게 되므로 손대지 않는다.
USING_RUNNING_DEV_SERVER = _server_already_running(TEST_PORT)

SESSION_DATABASE_URL = None
SESSION_DATABASE_NAME = None


def _isolate_database_url():
    """세션 전용 임시 DB 를 만들고 DATABASE_URL 을 거기로 박는다.

    ★셸이나 .env 의 DATABASE_URL 은 보지 않는다. 운영 주소가 들어 있어도 쓰지 않는다.
      관리 주소(TEST_DATABASE_ADMIN_URL)는 testing_db 가 로컬 호스트만 허용한다.
    ★스키마는 alembic upgrade 로 올린다. 서버가 lifespan 에서 다시 upgrade 해도 이미
      head 라 아무 일도 없다. create_all 이 아니라 기준점으로 올려야 마이그레이션도 검증된다.
    """
    global SESSION_DATABASE_URL, SESSION_DATABASE_NAME
    if USING_RUNNING_DEV_SERVER:
        return
    url = testing_db.create_database(prefix="ymtc_test")
    os.environ["DATABASE_URL"] = url
    os.environ.pop("DATABASE_URL_DIRECT", None)
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=os.path.dirname(os.path.abspath(__file__)),
                       env=dict(os.environ), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        testing_db.drop_database(url)
        raise RuntimeError(f"테스트 DB 마이그레이션 실패:\n{r.stderr}")
    SESSION_DATABASE_URL = url
    from sqlalchemy.engine import make_url
    SESSION_DATABASE_NAME = make_url(url).database
    atexit.register(testing_db.drop_database, url)


_isolate_database_url()
```

같은 파일 끝에 픽스처를 더한다.

```python
@pytest.fixture
def pg_engine():
    """테스트 하나 전용 스키마. SQLite 시절 tmp_path 마다 새 DB 파일을 만들던 자리다."""
    base = SESSION_DATABASE_URL or testing_db.create_database(prefix="ymtc_unit")
    eng = testing_db.schema_engine(base)
    try:
        yield eng
    finally:
        testing_db.dispose_schema_engine(eng)
        if SESSION_DATABASE_URL is None:
            testing_db.drop_database(base)


@pytest.fixture
def pg_session(pg_engine):
    from sqlalchemy.orm import sessionmaker
    session = sessionmaker(bind=pg_engine, autoflush=False)()
    try:
        yield session
    finally:
        session.close()
```

`.env` 의 `DATABASE_URL` 이 `env_setup` 을 통해 들어와도, 위 코드가 `os.environ` 을 먼저 덮으므로 `database.py` 임포트(테스트 모듈 수집 시점)는 임시 DB 를 본다. `env_setup` 은 `override=False` 라 덮지 않는다.

- [ ] **Step 4: 통과 확인**

Run: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_db_isolation.py test_dev_db_guard.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 이미 떠 있는 서버 모드 회귀 확인**

```bash
cd backend
DATABASE_URL=$(python -c "import testing_db; print(testing_db.create_database(prefix='ymtc_manual'))") \
  python -m uvicorn main:app --port 8018 &
sleep 5
TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_db_isolation.py -q
kill %1
```

Expected: `test_세션_DB...`, `test_앱_엔진...` 은 SKIP, 마지막 테스트는 PASS. 끝나면 `ymtc_manual_*` DB 를 `testing_db.drop_database` 로 지운다.

- [ ] **Step 6: 커밋**

```bash
git add backend/conftest.py backend/test_db_isolation.py backend/dev_db_guard.py
git commit -m "test: 서버 테스트 세션 DB 를 임시 PostgreSQL 로, 원격 주소 무시 (SYM-6)"
```

---

### Task 5: SQLite 엔진을 만들던 단위 테스트 전환

**Files:**
- Modify (DB 픽스처 교체): `test_tc_renumber_service.py`, `test_run_round_nullable.py`, `tests_unit/test_api_keys.py`, `tests_unit/test_dashboard_latest_executed.py`, `tests_unit/test_dashboard_rounds.py`, `tests_unit/test_dashboard_stability.py`, `tests_unit/test_dashboard_version.py`, `tests_unit/test_first_admin.py`, `tests_unit/test_overview_pass_rate.py`, `tests_unit/test_purge_keeps_run_history.py`, `tests_unit/test_report_compare_target.py`, `tests_unit/test_report_content.py`, `tests_unit/test_result_conflict.py`, `tests_unit/test_result_import.py`, `tests_unit/test_run_export_columns.py`, `tests_unit/test_run_issues.py`, `tests_unit/test_run_next_round.py`, `tests_unit/test_tc_id_dedup.py`, `tests_unit/test_unique_constraints.py`
- Modify (값만): `test_env_loading.py` (SQLite 주소 문자열을 PostgreSQL 형식으로)
- Delete (옛 마이그레이션 검증, `sqlite-legacy` 에 남음): `test_migration_preserves_schema.py`, `test_tc_no_normalize.py`, `tests_unit/test_migration_dedup_safety.py`, `tests_unit/test_schema_guard.py`, `tests_unit/test_unique_tc_id_migration.py`
- Modify (옛 마이그레이션 부분만 삭제): `test_result_uniqueness.py`, `tests_unit/test_run_issues.py`
- Modify: `test_account_requests.py:21-29`, `tests_unit/test_api_keys.py:106`, `test_run_tc_sync.py:266`
- Create: `backend/tests_unit/test_no_sqlite_in_tests.py`

**Interfaces:**
- Consumes: `pg_engine`, `pg_session` (Task 4)

- [ ] **Step 1: 가드 테스트 작성**

```python
"""테스트 소스에 SQLite 엔진이 남아 있으면 실패한다.

SQLite 엔진을 직접 만드는 테스트는 DATABASE_URL 과 무관하게 SQLite 에서 돌아,
PostgreSQL 에서 깨지는 코드를 통과시킨다(전환 전 27개 파일이 그랬다).
"""
import os
import re

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERN = re.compile(r"sqlite(\+\w+)?://|import sqlite3")
ALLOWED = {os.path.join("tests_unit", "test_no_sqlite_in_tests.py")}


def test_테스트에_sqlite_가_없다():
    hits = []
    for root, dirs, files in os.walk(BACKEND):
        dirs[:] = [d for d in dirs if d not in {"__pycache__", ".pytest_cache", "venv", ".venv"}]
        for f in files:
            if not (f.startswith("test_") and f.endswith(".py")) and f != "conftest.py":
                continue
            rel = os.path.relpath(os.path.join(root, f), BACKEND)
            if rel in ALLOWED:
                continue
            text = open(os.path.join(root, f), encoding="utf-8").read()
            for i, line in enumerate(text.splitlines(), 1):
                if PATTERN.search(line):
                    hits.append(f"{rel}:{i}: {line.strip()}")
    assert hits == [], "\n".join(hits)
```

Run: `cd backend && python -m pytest tests_unit/test_no_sqlite_in_tests.py -q`
Expected: FAIL, 27개 파일의 줄 목록

- [ ] **Step 2: 옛 마이그레이션 테스트 삭제**

```bash
cd backend
git rm -q test_migration_preserves_schema.py test_tc_no_normalize.py \
  tests_unit/test_migration_dedup_safety.py tests_unit/test_schema_guard.py \
  tests_unit/test_unique_tc_id_migration.py
```

`test_result_uniqueness.py` 와 `tests_unit/test_run_issues.py` 는 파일을 열어 alembic 리비전 파일을 직접 로드하거나 `alembic upgrade <옛 리비전>` 을 부르는 테스트 함수와 그 헬퍼(`_alembic`, `MIGRATION` 경로 상수, `import sqlite3`)만 지운다. 모델 수준의 유일성·동작 테스트는 남겨 Step 3 의 방식으로 바꾼다.

- [ ] **Step 3: DB 픽스처를 공용 픽스처로 교체**

각 파일의 SQLite 픽스처는 두 모양이다. 모양에 맞게 바꾼다.

모양 A, 세션을 돌려주는 `db` 픽스처:

```python
# 전
@pytest.fixture
def db(tmp_path):
    url = f"sqlite:///{tmp_path / 'admin.db'}".replace("\\", "/")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()

# 후
@pytest.fixture
def db(pg_session):
    yield pg_session
```

모양 B, 엔진을 만들어 `app.dependency_overrides[get_db]` 에 세션 팩토리를 넣는 픽스처(`test_api_keys.py`, `test_dashboard_*`, `test_overview_pass_rate.py`, `test_result_conflict.py`, `test_result_import.py`, `test_run_next_round.py`):

```python
# 전
    engine = create_engine(f"sqlite:///{(tmp_path / 'keys.db').as_posix()}", connect_args={"check_same_thread": False})
    ...
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

# 후 (픽스처 인자에 pg_engine 을 더하고 tmp_path 는 다른 용도가 없으면 뺀다)
    engine = pg_engine
    Session = sessionmaker(bind=engine)
```

`engine.dispose()` 나 파일 삭제 정리 코드는 지운다. 정리는 `pg_engine` 이 한다. 쓰지 않게 된 `create_engine` 임포트를 지운다.

`test_tc_id_dedup.py` 는 모듈 수준에서 `models` 를 임포트하므로 conftest 이후에 임포트되는지만 확인한다(conftest 가 먼저 로드되므로 그대로 둬도 된다).

`test_env_loading.py` 는 엔진을 만들지 않고 `.env` 로딩 순서만 본다. 주소 문자열 두 개를 바꾼다.

```python
# 전
    env_file.write_text("DATABASE_URL=sqlite:///./from_file.db\n", encoding="utf-8")
    env["DATABASE_URL"] = "sqlite:///./from_real_env.db"
    assert r.stdout.strip() == "sqlite:///./from_real_env.db"
# 후
    env_file.write_text("DATABASE_URL=postgresql+psycopg2://u:p@127.0.0.1:1/from_file\n", encoding="utf-8")
    env["DATABASE_URL"] = "postgresql+psycopg2://u:p@127.0.0.1:1/from_real_env"
    assert r.stdout.strip() == "postgresql+psycopg2://u:p@127.0.0.1:1/from_real_env"
```

- [ ] **Step 4: 메모리 상태를 직접 지우던 픽스처 정리**

`test_account_requests.py:21-29` 의 `except ImportError: pass` 픽스처와 `tests_unit/test_api_keys.py:106` 의 `_login_failures.clear()` 는 이 계획에서는 그대로 둔다(메모리 상태는 아직 있다). 계획 2 에서 DB 테이블로 옮길 때 같은 커밋에서 바꾼다. 대신 `except ImportError: pass` 를 지워 임포트가 실패하면 테스트가 바로 깨지게 한다.

`test_run_tc_sync.py:266` 의 `PRAGMA busy_timeout` 검사 테스트 함수를 지운다.

- [ ] **Step 5: 통과 확인**

Run: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest tests_unit/test_no_sqlite_in_tests.py -q`
Expected: PASS

Run: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest tests_unit -q -x`
Expected: `test_tc_renumber_service.py` 는 루트에 있어 여기 안 잡힌다. `tests_unit` 의 실패는 PostgreSQL 에서 실제로 깨지는 코드다. 실패 목록을 그대로 Task 8 로 넘긴다. 이 Task 에서 앱 코드를 고치지 않는다.

- [ ] **Step 6: 커밋**

```bash
git add -A backend
git commit -m "test: SQLite 엔진을 만들던 테스트 27개를 PostgreSQL 픽스처로 (SYM-6)"
```

---

### Task 6: renumber_sheet 를 PostgreSQL 로

**Files:**
- Modify: `backend/services/tc_numbering.py:72-101`
- Test: `backend/test_tc_renumber_service.py` (Task 5 에서 전환됨)

**Interfaces:**
- Consumes: `pg_session`
- Produces: `renumber_sheet(project_id: int, sheet_name: str, db: Session) -> None` (시그니처 그대로)

- [ ] **Step 1: 실패 확인**

Run: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_tc_renumber_service.py -q`
Expected: FAIL, `schema "temp" does not exist` 또는 `relation "_tc_rank" does not exist`

- [ ] **Step 2: 소프트 삭제가 섞인 경우의 테스트 추가**

`test_tc_renumber_service.py` 끝에 더한다. 파일의 기존 헬퍼 이름을 확인해 TC 생성 헬퍼가 다르면 그 이름을 쓴다.

```python
def test_소프트_삭제가_섞여도_살아_있는_TC_가_1부터_이어진다(db):
    from datetime import datetime
    from models import Project, TestCase, User
    from services.tc_numbering import renumber_sheet

    u = User(username="u", password_hash="x", display_name="u")
    db.add(u); db.flush()
    p = Project(name="p", created_by=u.id)
    db.add(p); db.flush()
    rows = []
    for i, no in enumerate([5, 2, 9, 7], 1):
        tc = TestCase(project_id=p.id, sheet_name="S", tc_id=f"TC-{i}", no=no, created_by=u.id)
        db.add(tc); rows.append(tc)
    db.flush()
    rows[1].deleted_at = datetime(2026, 1, 1)
    db.flush()

    renumber_sheet(p.id, "S", db)
    db.flush()
    for r in rows:
        db.refresh(r)
    live = sorted((r.no, r.tc_id) for r in rows if r.deleted_at is None)
    assert live == [(1, "TC-1"), (2, "TC-4"), (3, "TC-3")]
```

`Project`, `TestCase` 의 필수 칸이 이 예시와 다르면 `models.py` 의 `nullable=False` 칸을 채운다.

- [ ] **Step 3: 구현**

`renumber_sheet` 를 바꾼다.

```python
def renumber_sheet(project_id: int, sheet_name: str, db: Session) -> None:
    """한 시트의 no 를 1 부터 다시 매긴다. 지금 차례는 변경하지 않는다.

    ★두 문장으로 나눈다. PostgreSQL 은 유니크 제약을 행마다 즉시 검사하므로, 목표 번호를
      다른 행이 아직 쥐고 있으면 걸린다. 먼저 전부 비켜 두고 그 다음에 쓴다.
    ★순위는 첫 문장에서 한 번만 매긴다. UPDATE ... FROM 의 부분 질의는 문장 시작 시점의
      스냅숏을 읽으므로 이미 바꾼 값 위에서 순위가 다시 매겨지지 않는다. 둘째 문장은
      비켜 둔 값에서 순위를 되읽는다(no = -floor - rn).
    """
    floor = _park_floor(project_id, sheet_name, db)
    db.execute(
        text(f"""
            UPDATE test_cases AS t
            SET no = -:floor - r.rn
            FROM (
                SELECT id, ROW_NUMBER() OVER (ORDER BY {_ORDER}) AS rn
                FROM test_cases
                WHERE project_id = :pid AND sheet_name = :sheet
            ) AS r
            WHERE t.id = r.id
        """),
        {"pid": project_id, "sheet": sheet_name, "floor": floor},
    )
    db.execute(
        text("""
            UPDATE test_cases
            SET no = -no - :floor
            WHERE project_id = :pid AND sheet_name = :sheet
        """),
        {"pid": project_id, "sheet": sheet_name, "floor": floor},
    )
```

모듈 docstring 의 "SQLite 는 행 단위로 검사한다" 를 "유니크 제약은 행 단위로 즉시 검사된다" 로 고친다.

- [ ] **Step 4: 통과 확인**

Run: `cd backend && TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest test_tc_renumber_service.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add backend/services/tc_numbering.py backend/test_tc_renumber_service.py
git commit -m "fix: 시트 재번호에서 SQLite 임시 테이블 제거 (SYM-6)"
```

---

### Task 7: 고급 필터의 칸 타입별 연산자

**Files:**
- Modify: `backend/routes/filters.py:116-153`
- Test: `backend/tests_unit/test_filter_types.py`

**Interfaces:**
- Produces: `_apply_condition(q, field, operator, value)` 가 타입에 맞지 않는 조합에 `HTTPException(400)` 을 던진다

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""정수 칸 no 에 문자열 연산을 걸면 400. SQLite 는 넘어갔지만 PostgreSQL 은 500 이었다."""
import os
import sys

import pytest
from fastapi import HTTPException

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND not in sys.path:
    sys.path.insert(0, BACKEND)

from models import TestCase
from routes.filters import _apply_condition


@pytest.mark.parametrize("op,value", [("contains", "1"), ("not_contains", "1"), ("empty", None), ("not_empty", None)])
def test_정수_칸에_문자열_연산은_400(pg_session, op, value):
    q = pg_session.query(TestCase)
    with pytest.raises(HTTPException) as e:
        _apply_condition(q, "no", op, value)
    assert e.value.status_code == 400


@pytest.mark.parametrize("value", ["abc", "1.5", ""])
def test_정수_칸에_숫자가_아닌_값은_400(pg_session, value):
    with pytest.raises(HTTPException) as e:
        _apply_condition(pg_session.query(TestCase), "no", "gt", value)
    assert e.value.status_code == 400


def test_정수_칸_비교는_실행된다(pg_session):
    q = _apply_condition(pg_session.query(TestCase), "no", "gte", "3")
    assert q.all() == []


def test_정수_칸_in_은_정수로_바꾼다(pg_session):
    q = _apply_condition(pg_session.query(TestCase), "no", "in", ["1", "2"])
    assert q.all() == []


def test_문자열_칸의_포함은_그대로(pg_session):
    q = _apply_condition(pg_session.query(TestCase), "tc_id", "contains", "TC")
    assert q.all() == []
```

Run: `cd backend && python -m pytest tests_unit/test_filter_types.py -q`
Expected: FAIL (400 대신 예외 없음, 또는 PostgreSQL 오류)

- [ ] **Step 2: 구현**

`VALID_FIELDS` 아래에 정수 칸 집합과 변환 함수를 두고 `_apply_condition` 앞부분을 바꾼다.

```python
#: 정수 칸. 문자열 연산(포함/빈 값)이 의미가 없고 값은 정수로 바꿔 비교한다.
INT_FIELDS = {"no"}
_INT_OPERATORS = {"eq", "neq", "gt", "lt", "gte", "lte", "in"}


def _to_int(value):
    try:
        if isinstance(value, bool):
            raise ValueError
        if isinstance(value, int):
            return value
        s = str(value).strip()
        if not s.lstrip("-").isdigit():
            raise ValueError
        return int(s)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail=f"숫자 칸에는 정수만 쓸 수 있습니다: {value!r}")


def _apply_condition(q, field: str, operator: str, value):
    """단일 조건을 쿼리에 적용"""
    if field not in VALID_FIELDS:
        return q

    col = getattr(TestCase, field, None)
    if col is None:
        return q

    if field in INT_FIELDS:
        if operator not in _INT_OPERATORS:
            raise HTTPException(status_code=400, detail=f"숫자 칸에는 '{operator}' 조건을 쓸 수 없습니다")
        value = [_to_int(v) for v in value] if operator == "in" and isinstance(value, list) else (
            value if operator == "in" else _to_int(value))
```

그 아래 기존 `if operator == "eq": ...` 분기는 그대로 둔다. 파일 상단에 `from fastapi import HTTPException` 이 없으면 더한다.

- [ ] **Step 3: 통과 확인**

Run: `cd backend && python -m pytest tests_unit/test_filter_types.py -q`
Expected: `10 passed`

- [ ] **Step 4: 커밋**

```bash
git add backend/routes/filters.py backend/tests_unit/test_filter_types.py
git commit -m "fix: 고급 필터 숫자 칸에 문자열 연산 시 400 (SYM-6)"
```

---

### Task 8: 전체 스위트를 PostgreSQL 에서 통과시키기

**Files:**
- Modify: 실패가 가리키는 앱 코드
- Modify: `backend/services/run_sync_service.py:27-35` (SQLite 분기 제거)

- [ ] **Step 1: run_sync_service 의 SQLite 분기 제거**

```python
    from sqlalchemy.dialects.postgresql import insert as _insert
    stmt = _insert(TestResult).values(rows).on_conflict_do_nothing(
        index_elements=["test_run_id", "test_case_id"]
    )
```

`dialect` 판별과 `NotImplementedError` 분기를 지우고, docstring 의 "SQLite 와 PostgreSQL 둘 다" 문장을 "PostgreSQL 의 ON CONFLICT DO NOTHING 을 쓴다" 로 고친다.

- [ ] **Step 2: 전체 실행**

```bash
cd backend
TEST_PORT=8018 TEST_BASE_URL=http://127.0.0.1:8018 python -m pytest -q --tb=short -k "not test_dompurify_installed" 2>&1 | tee /tmp/pg_full.txt | tail -40
```

- [ ] **Step 3: 실패를 하나씩 원인부터**

실패마다 superpowers:systematic-debugging 으로 원인을 찾는다. 이미 실패하는 테스트가 있으므로 새 테스트는 필요 없고, 원인이 테스트에 없는 동작이면 그 동작을 고정하는 테스트를 먼저 더한다. 예상되는 유형과 처리:

- 정렬 결과 차이(NULL 위치, collation): 앱 쿼리에 `nulls_last()` 같은 명시를 넣어 지금 화면 결과를 유지한다. 테스트의 기대값을 바꾸지 않는다.
- 타입 엄격성(문자열과 정수 비교, 빈 문자열을 정수 칸에): 앱에서 값을 변환하거나 400 으로 거절한다.
- `GROUP BY` 오류: 비집계 칸을 그룹 키에 넣거나 집계로 감싼다.
- IntegrityError 메시지 판정(`main.py:120`, `routes/testruns.py:465`): PostgreSQL 메시지에 제약 이름이 들어가므로 이름 판정이 동작하는지 확인하고, SQLite 형식 문자열 분기(`"test_cases.project_id, test_cases.tc_id"`)를 지운다.

실패 한 건을 고칠 때마다 그 테스트 파일만 다시 돌리고, 묶음이 끝나면 전체를 다시 돌린다.

- [ ] **Step 4: 전체 통과 확인**

Run: Step 2 와 같은 명령
Expected: `failed` 0, `error` 0. `skipped` 가 SQLite 시절보다 늘었으면 늘어난 이유를 하나씩 확인한다(새 skip 은 결함을 숨긴다).

- [ ] **Step 5: 커밋**

고친 유형별로 나눠 커밋한다. 예:

```bash
git add backend/services/run_sync_service.py
git commit -m "refactor: 결과 행 일괄 생성에서 SQLite 분기 제거 (SYM-6)"
```

---

### Task 9: devctl 과 로컬 구동

**Files:**
- Modify: `scripts/devctl.py`
- Modify: `.claude/skills/dev/SKILL.md`, `CLAUDE.md` 의 로컬 구동 절
- Test: `scripts/test_devctl_db.py`

**Interfaces:**
- Produces: `devctl.ensure_database() -> None`: compose 의 `db` 를 띄우고 healthy 까지 기다린다. Docker 가 없거나 꺼져 있으면 안내 문구와 함께 `SystemExit(2)`

- [ ] **Step 1: 실패하는 테스트 작성**

```python
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import devctl


def test_docker_가_없으면_안내하고_멈춘다(monkeypatch, capsys):
    def boom(*a, **k):
        raise FileNotFoundError("docker")
    monkeypatch.setattr(devctl.subprocess, "run", boom)
    with pytest.raises(SystemExit) as e:
        devctl.ensure_database()
    assert e.value.code == 2
    assert "Docker" in capsys.readouterr().err


def test_데몬이_꺼져_있으면_안내하고_멈춘다(monkeypatch, capsys):
    monkeypatch.setattr(devctl.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "Cannot connect to the Docker daemon"))
    with pytest.raises(SystemExit) as e:
        devctl.ensure_database()
    assert e.value.code == 2
    assert "Docker Desktop" in capsys.readouterr().err
```

Run: `python -m pytest scripts/test_devctl_db.py -q`
Expected: FAIL, `AttributeError: module 'devctl' has no attribute 'ensure_database'`

- [ ] **Step 2: 구현**

`devctl.py` 에 더하고 `cmd_up` 첫 줄에서 부른다.

```python
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def ensure_database() -> None:
    """로컬 PostgreSQL(docker compose 의 db) 을 띄우고 준비될 때까지 기다린다."""
    try:
        r = subprocess.run(["docker", "compose", "up", "-d", "--wait", "db"],
                           cwd=REPO_ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("Docker 가 설치되어 있지 않습니다. Docker Desktop 을 설치하세요.", file=sys.stderr)
        raise SystemExit(2)
    if r.returncode != 0:
        print("PostgreSQL 컨테이너를 띄우지 못했습니다. Docker Desktop 이 실행 중인지 확인하세요.\n"
              + (r.stderr or r.stdout), file=sys.stderr)
        raise SystemExit(2)
```

- [ ] **Step 3: 통과 확인**

Run: `python -m pytest scripts/test_devctl_db.py -q`
Expected: `2 passed`

실제 구동: `python scripts/devctl.py up` 후 `python scripts/devctl.py api GET /api/projects` 가 200, 끝나면 `python scripts/devctl.py down`. 이 단계는 worktree 의 `backend/.env` 에 Task 2 의 로컬 PostgreSQL 주소가 있어야 한다(`.env` 는 커밋하지 않는다).

- [ ] **Step 4: 문서 수정**

`CLAUDE.md` 로컬 구동 절과 `.claude/skills/dev/SKILL.md` 에서 "DB 는 backend/tc_manager.db", "BEGIN IMMEDIATE", "PRAGMA busy_timeout" 서술을 지우고 아래로 바꾼다.

```
DB 는 docker compose 의 PostgreSQL(127.0.0.1:54329)이다. devctl up 이 컨테이너를 먼저 띄운다.
Docker Desktop 이 꺼져 있으면 up 이 안내하고 멈춘다.
```

- [ ] **Step 5: 커밋**

```bash
git add scripts/devctl.py scripts/test_devctl_db.py CLAUDE.md .claude/skills/dev/SKILL.md
git commit -m "chore: devctl up 이 로컬 PostgreSQL 을 먼저 띄운다 (SYM-6)"
```

---

### Task 10: CI 를 PostgreSQL 로

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: backend 잡에 서비스 컨테이너**

```yaml
  backend:
    name: Backend (pytest)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env:
          POSTGRES_USER: ymtc
          POSTGRES_PASSWORD: ymtc
          POSTGRES_DB: ymtc
        ports: ["54329:5432"]
        options: >-
          --health-cmd "pg_isready -U ymtc -d ymtc"
          --health-interval 2s --health-timeout 3s --health-retries 30
```

pytest 단계 env 에 `TEST_DATABASE_ADMIN_URL: postgresql+psycopg2://ymtc:ymtc@localhost:54329/ymtc` 를 더한다. 이미지 태그는 Task 1 Step 1 에서 정한 값과 같게 한다.

- [ ] **Step 2: e2e 잡**

같은 `services.postgres` 블록을 더하고, Start backend 단계에 `env: DATABASE_URL: postgresql+psycopg2://ymtc:ymtc@localhost:54329/ymtc` 를 준다. lifespan 이 기동 시 기준점까지 올린다. 관리자 시드는 지금처럼 `/api/auth/register` 를 쓴다(공개 가입 제거는 하위 프로젝트 2).

- [ ] **Step 3: install-matrix 잡**

Import check 의 `DATABASE_URL: sqlite:///./ci_import_check.db` 를 `DATABASE_URL: postgresql+psycopg2://u:p@127.0.0.1:1/import_check` 로 바꾼다. 임포트만 하고 접속하지 않으므로 서버가 없어도 된다(`create_engine` 은 지연 접속).

- [ ] **Step 4: 원격에서 확인**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: 테스트와 E2E 를 PostgreSQL 서비스 컨테이너로 (SYM-6)"
git push -u origin feat/postgresql
gh run list --branch feat/postgresql --limit 1
```

`ci.yml` 의 트리거가 `main` 브랜치 push 와 `main` 대상 PR 뿐이라 브랜치 push 로는 돌지 않는다. `on.push.branches` 에 `feat/**` 를 더하거나 `gh workflow run` 을 쓸 수 있도록 `workflow_dispatch:` 를 더해 실행한다. 네 잡이 모두 성공하는지 `gh run watch` 로 본다.

---

## 계획 1 완료 조건

- `python -m pytest -q` 가 로컬 PostgreSQL 에서 실패 0, 에러 0
- 테스트 소스에 `sqlite://` 0건 (가드 테스트)
- 앱 코드에서 `grep -rn "sqlite\|PRAGMA" backend --include=*.py` 결과가 주석과 테스트 가드 외 0건
- CI 네 잡 성공
- QA 2인 검증 통과 후 계획 2 로 넘어간다
