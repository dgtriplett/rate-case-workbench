"""Bootstrap the Lakebase schema from SQLAlchemy models.

Usage:
    DATABRICKS_PROFILE=fe-vm-grid-ops-demo \
    PGHOST=ep-polished-wave-d142x9tw.database.us-west-2.cloud.databricks.com \
    PGUSER=drew.triplett@databricks.com \
    PGDATABASE=databricks_postgres \
    python -m seed.bootstrap_db

Subsequent schema changes should use Alembic migrations under backend/migrations.
"""
from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

import sys
from pathlib import Path

import os
try:
    _SCRIPT_ROOT = Path(__file__).resolve().parent.parent
except NameError:
    _SCRIPT_ROOT = Path(os.environ.get("RCW_PROJECT_ROOT", "/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench"))
sys.path.insert(0, str(_SCRIPT_ROOT))

from backend.databricks_client import get_oauth_token  # noqa: E402
from backend.models import Base, Role, RoleKey  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")
log = logging.getLogger("bootstrap")


def _build_url() -> str:
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "databricks_postgres")
    user = os.environ.get("PGUSER")
    if not host or not user:
        raise SystemExit("PGHOST and PGUSER must be set")
    token = get_oauth_token()
    return f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(token)}@{host}:{port}/{db}"


async def main() -> None:
    url = _build_url()
    log.info("Connecting to Lakebase…")
    engine = create_async_engine(url, connect_args={"ssl": "require"})

    async with engine.begin() as conn:
        log.info("Creating extensions (pgcrypto for gen_random_uuid)…")
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    async with engine.begin() as conn:
        log.info("Creating tables…")
        await conn.run_sync(Base.metadata.create_all)

    async with engine.begin() as conn:
        log.info("Seeding roles…")
        for rk in RoleKey:
            await conn.execute(
                text(
                    "INSERT INTO roles (key, description) VALUES (:k, :d) "
                    "ON CONFLICT (key) DO NOTHING"
                ),
                {"k": rk.value, "d": rk.value.replace("_", " ").title()},
            )

    await engine.dispose()
    log.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
