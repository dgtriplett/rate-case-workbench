"""Tools for the position checker — reads agent_memory for the case."""
from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy import text

try:
    import mlflow

    trace = mlflow.trace  # type: ignore[attr-defined]
except Exception:  # pragma: no cover

    def trace(func=None, **_kw):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func


from ..common.lakebase import session_scope


async def _load_async(case_id: str, jurisdiction: Optional[str]) -> list[dict]:
    async with session_scope() as sess:
        res = await sess.execute(
            text(
                "SELECT id::text, case_id::text, jurisdiction, topic_key, fact_text, "
                "rationale, confidence "
                "FROM agent_memory "
                "WHERE is_active = TRUE "
                "AND (case_id = CAST(:case_id AS uuid) OR jurisdiction = :jurisdiction) "
                "ORDER BY confidence DESC LIMIT 100"
            ),
            {"case_id": case_id, "jurisdiction": jurisdiction},
        )
        return [dict(r) for r in res.mappings().all()]


@trace(name="load_memory_for_case")
def load_memory_for_case(case_id: str, jurisdiction: Optional[str] = None) -> list[dict]:
    try:
        return asyncio.run(_load_async(case_id, jurisdiction))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_load_async(case_id, jurisdiction))
        finally:
            loop.close()
