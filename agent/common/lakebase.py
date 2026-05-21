"""Async Lakebase Postgres helper for agents.

Mirrors backend/db.py but is a standalone copy so agents can be deployed without
shipping the FastAPI backend.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional
from urllib.parse import quote_plus

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .llm import _workspace  # reuse workspace client resolver

log = logging.getLogger(__name__)

_TOKEN_TTL_SECONDS = 45 * 60


def _oauth_token() -> str:
    wc = _workspace()
    headers = wc.config.authenticate()
    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return wc.config.token or ""


class _LakebaseEngine:
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._sm: Optional[async_sessionmaker[AsyncSession]] = None
        self._obtained_at: float = 0.0
        self._lock = asyncio.Lock()

    def _url(self, token: str) -> str:
        host = os.environ.get("PGHOST", "")
        port = os.environ.get("PGPORT", "5432")
        db = os.environ.get("PGDATABASE", "databricks_postgres")
        user = os.environ.get("PGUSER", "")
        if not host or not user:
            raise RuntimeError("PGHOST and PGUSER must be set for Lakebase access")
        return (
            f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(token)}@{host}:{port}/{db}"
        )

    async def _build(self) -> None:
        token = _oauth_token()
        url = self._url(token)
        eng = create_async_engine(
            url,
            pool_size=3,
            max_overflow=5,
            pool_pre_ping=True,
            connect_args={
                "ssl": "require",
                "server_settings": {"application_name": "rcw-agent"},
            },
        )
        self._engine = eng
        self._sm = async_sessionmaker(eng, expire_on_commit=False, class_=AsyncSession)
        self._obtained_at = time.time()

    async def ensure(self) -> async_sessionmaker[AsyncSession]:
        async with self._lock:
            stale = (time.time() - self._obtained_at) > _TOKEN_TTL_SECONDS
            if self._engine is None or stale:
                if self._engine is not None:
                    await self._engine.dispose()
                await self._build()
            assert self._sm is not None
            return self._sm

    async def dispose(self) -> None:
        async with self._lock:
            if self._engine is not None:
                await self._engine.dispose()
                self._engine = None
                self._sm = None


_lb = _LakebaseEngine()


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    sm = await _lb.ensure()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def shutdown() -> None:
    await _lb.dispose()
