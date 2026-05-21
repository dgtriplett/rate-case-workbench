"""Alembic env that uses the live Lakebase token at migration time."""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.databricks_client import get_oauth_token  # noqa: E402
from backend.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _build_url() -> str:
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "databricks_postgres")
    user = os.environ.get("PGUSER")
    if not host or not user:
        raise RuntimeError("PGHOST and PGUSER must be set for Alembic")
    token = get_oauth_token()
    return f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(token)}@{host}:{port}/{db}"


target_metadata = Base.metadata


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=False,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _build_url()
    cfg["sqlalchemy.connect_args"] = {"ssl": "require"}
    connectable = async_engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


run_migrations_online()
