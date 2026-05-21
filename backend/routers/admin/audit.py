from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import Event
from ...schemas import EventOut

router = APIRouter(prefix="/audit", tags=["admin-audit"])


@router.get("/events", response_model=list[EventOut])
async def list_events(
    session: DBSession,
    _: RequireAdmin,
    case_id: Optional[uuid.UUID] = Query(default=None),
    target_kind: Optional[str] = Query(default=None),
    limit: int = Query(default=200, le=2000),
) -> list[EventOut]:
    q = select(Event).order_by(Event.created_at.desc()).limit(limit)
    if case_id:
        q = q.where(Event.case_id == case_id)
    if target_kind:
        q = q.where(Event.target_kind == target_kind)
    res = await session.execute(q)
    return [EventOut.model_validate(e) for e in res.scalars().all()]
