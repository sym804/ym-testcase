import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import env_setup  # noqa: F401  # .env 로딩

from database import Base
import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# 마이그레이션은 트랜잭션 풀러를 피해 직결(또는 세션 풀러) 주소로 한다.
# 둘 다 없으면 멈춘다. 빈 값으로 진행하면 엉뚱한 곳에 "성공" 할 수 있다.
db_url = os.getenv("DATABASE_URL_DIRECT") or os.getenv("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL_DIRECT 또는 DATABASE_URL 이 필요하다")
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
