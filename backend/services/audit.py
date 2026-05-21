"""Audit event writer. Every state-change in the app emits an Event row.

A nightly Databricks Job (rcw-cdc-audit) mirrors events to Delta tables in
`grid_ops_demo_catalog.rcw_audit.*` for permanent UC-governed audit lineage.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Event, User


async def log_event(
    session: AsyncSession,
    *,
    actor: Optional[User],
    verb: str,
    target_kind: str,
    target_id: Optional[uuid.UUID] = None,
    case_id: Optional[uuid.UUID] = None,
    payload: Optional[dict[str, Any]] = None,
) -> Event:
    ev = Event(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        verb=verb,
        target_kind=target_kind,
        target_id=target_id,
        case_id=case_id,
        payload=payload or {},
    )
    session.add(ev)
    await session.flush()
    return ev
