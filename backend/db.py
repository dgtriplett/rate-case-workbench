"""Lakebase async SQLAlchemy engine with OAuth token rotation (tokens expire ~1h)."""
import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .config import get_settings
from .databricks_client import get_lakebase_token

log = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS = 45 * 60


class LakebaseEngine:
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None
        self._token_obtained_at: float = 0.0
        self._lock = asyncio.Lock()

    def _build_url(self, token: str) -> str:
        s = get_settings()
        user = s.pguser or os.environ.get("PGUSER", "")
        host = s.pghost or os.environ.get("PGHOST", "")
        port = s.pgport or int(os.environ.get("PGPORT", "5432"))
        db = s.pgdatabase or os.environ.get("PGDATABASE", "databricks_postgres")
        from urllib.parse import quote_plus
        return (
            f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(token)}@{host}:{port}/{db}"
        )

    async def _create(self) -> None:
        token = get_lakebase_token()
        url = self._build_url(token)
        engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            connect_args={
                "ssl": "require",
                "server_settings": {
                    "application_name": "rate-case-workbench",
                    "search_path": "rcw,public",
                },
            },
        )
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        self._token_obtained_at = time.time()
        log.info("Lakebase engine created (token rotated)")

    async def ensure(self) -> async_sessionmaker[AsyncSession]:
        async with self._lock:
            stale = (time.time() - self._token_obtained_at) > _TOKEN_TTL_SECONDS
            if self._engine is None or stale:
                if self._engine is not None:
                    await self._engine.dispose()
                await self._create()
            assert self._sessionmaker is not None
            return self._sessionmaker

    async def dispose(self) -> None:
        async with self._lock:
            if self._engine is not None:
                await self._engine.dispose()
                self._engine = None
                self._sessionmaker = None


_lakebase = LakebaseEngine()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    sm = await _lakebase.ensure()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


async def shutdown_db() -> None:
    await _lakebase.dispose()
