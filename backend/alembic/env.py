import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import env_setup  # noqa: F401  # .env 로딩

from sqlalchemy.engine import make_url

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1", None}

# 마이그레이션은 트랜잭션 풀러를 피해 직결(또는 세션 풀러) 주소로 한다.
# 둘 다 없으면 멈춘다. 빈 값으로 진행하면 엉뚱한 곳에 "성공" 할 수 있다.
_app_url = os.getenv("DATABASE_URL")
_direct_url = os.getenv("DATABASE_URL_DIRECT")
db_url = _direct_url or _app_url
if not db_url:
    raise RuntimeError("DATABASE_URL_DIRECT 또는 DATABASE_URL 이 필요하다")

# ★앱은 로컬을 보는데 직결 주소만 원격이면 멈춘다. 로컬 .env 에 운영 직결 주소를 적어
#   두면 로컬 서버를 켤 때마다(기동 시 upgrade) 운영 DB 에 마이그레이션이 간다.
if _app_url and _direct_url:
    if (make_url(_app_url).host in _LOCAL_HOSTS) != (make_url(_direct_url).host in _LOCAL_HOSTS):
        raise RuntimeError(
            "DATABASE_URL 과 DATABASE_URL_DIRECT 중 하나만 원격이다. "
            "로컬 개발에서는 DATABASE_URL_DIRECT 를 비운다."
        )

# database 모듈은 DATABASE_URL 을 필수로 읽는다. 배포 워크플로처럼 직결 주소만 준
# 경우에도 모델을 불러올 수 있게 같은 값을 넘긴다. 엔진은 지연 접속이라 여기서 연결하지 않는다.
os.environ.setdefault("DATABASE_URL", db_url)

from database import Base  # noqa: E402
import models  # noqa: F401,E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
