import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

# Ensure the backend directory is on sys.path so 'app' is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
import app.models  # noqa: F401 — register all models with Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

database_url = os.getenv(
    "DATABASE_URL",
    config.get_main_option("sqlalchemy.url", "sqlite:///./zeropath.db"),
)


def run_migrations_offline():
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    async_url = database_url
    if "sqlite:///" in async_url and "+aiosqlite" not in async_url:
        async_url = async_url.replace("sqlite:///", "sqlite+aiosqlite:///")

    connectable = create_async_engine(async_url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online():
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
