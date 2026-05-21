"""Agent memory — Lakebase-backed per-case + cross-case position store."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import AgentMemory


async def list_for_case(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    topic_key: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    include_jurisdiction: bool = True,
    limit: int = 200,
) -> list[AgentMemory]:
    case_clause = AgentMemory.case_id == case_id
    if include_jurisdiction and jurisdiction:
        clause = or_(
            case_clause,
            and_(AgentMemory.case_id.is_(None), AgentMemory.jurisdiction == jurisdiction),
        )
    else:
        clause = case_clause
    q = select(AgentMemory).where(AgentMemory.is_active == True).where(clause)  # noqa: E712
    if topic_key:
        q = q.where(AgentMemory.topic_key == topic_key)
    q = q.order_by(AgentMemory.created_at.desc()).limit(limit)
    res = await session.execute(q)
    return list(res.scalars().all())


async def write(
    session: AsyncSession,
    *,
    case_id: Optional[uuid.UUID],
    jurisdiction: Optional[str],
    topic_key: str,
    fact_text: str,
    rationale: Optional[str] = None,
    source_response_id: Optional[uuid.UUID] = None,
    source_testimony_id: Optional[uuid.UUID] = None,
    source_document_id: Optional[uuid.UUID] = None,
    confidence: float = 0.8,
    created_by_agent_run_id: Optional[str] = None,
) -> AgentMemory:
    mem = AgentMemory(
        case_id=case_id,
        jurisdiction=jurisdiction,
        topic_key=topic_key,
        fact_text=fact_text,
        rationale=rationale,
        source_response_id=source_response_id,
        source_testimony_id=source_testimony_id,
        source_document_id=source_document_id,
        confidence=confidence,
        created_by_agent_run_id=created_by_agent_run_id,
    )
    session.add(mem)
    await session.flush()
    return mem


async def supersede(session: AsyncSession, old_id: uuid.UUID, new_id: uuid.UUID) -> None:
    res = await session.execute(select(AgentMemory).where(AgentMemory.id == old_id))
    old = res.scalar_one_or_none()
    if old is None:
        return
    old.is_active = False
    old.superseded_by = new_id
    await session.flush()
