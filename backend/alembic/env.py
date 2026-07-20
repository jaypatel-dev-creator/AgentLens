from logging.config import fileConfig
import os
import sys

from sqlalchemy import create_engine, pool
from alembic import context

# Add backend/ to path so app imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.core.config import get_settings

settings = get_settings()

# Build sync URL — Alembic is sync-only, never uses the async engine from base.py
if settings.database_url:
    sync_url = settings.database_url.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    ).replace(
        "postgres://", "postgresql+psycopg2://"
    )
else:
    # sqlite+aiosqlite → sqlite (sync driver, no aiosqlite needed)
    sync_url = f"sqlite:///{settings.sqlite_db_path}"

config = context.config
config.set_main_option("sqlalchemy.url", sync_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import models to expose Base.metadata — base.py's async engine is never used here
from app.db.base import Base
from app.db import models  # noqa: F401

target_metadata = Base.metadata


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
    # Use our own sync engine — never the async one from base.py
    connectable = create_engine(sync_url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,  # required for SQLite ALTER TABLE support
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()