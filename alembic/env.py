import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Add project root to path so we can import models
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Import the correct Base and models
from suno.database import Base
import suno.common.models  # noqa: F401 — ensure SUNO models are registered (User, Tier, Membership, etc)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Read DATABASE_URL from env and convert asyncpg -> psycopg2 for sync alembic
_db_url = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://suno:suno@localhost:5432/suno_clips",
)
# Alembic needs a sync driver
_sync_url = _db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://").replace(
    "postgresql://", "postgresql+psycopg2://"
)
config.set_main_option("sqlalchemy.url", _sync_url)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
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
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
