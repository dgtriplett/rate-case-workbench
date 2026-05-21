"""Live presence — track who's viewing/editing what right now."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import delete, select

from ..deps import CurrentUser, DBSession
from ..models import PresenceRecord, User

router = APIRouter(prefix="/presence", tags=["presence"])

# A user is "active" if their last heartbeat is within this window.
ACTIVE_WINDOW = timedelta(seconds=45)


class PresenceUser(BaseModel):
    user_id: uuid.UUID
    email: str
    display_name: str
    seconds_since_heartbeat: int


class PresenceOut(BaseModel):
    target_kind: str
    target_id: uuid.UUID
    viewers: list[PresenceUser]


class HeartbeatIn(BaseModel):
    target_kind: str
    target_id: uuid.UUID


@router.post("/heartbeat", response_model=PresenceOut)
async def heartbeat(body: HeartbeatIn, session: DBSession, user: CurrentUser) -> PresenceOut:
    now = datetime.now(timezone.utc)
    # Upsert my presence record
    existing = (await session.execute(
        select(PresenceRecord).where(
            PresenceRecord.user_id == user.id,
            PresenceRecord.target_kind == body.target_kind,
            PresenceRecord.target_id == body.target_id,
        )
    )).scalar_one_or_none()
    if existing:
        existing.last_heartbeat = now
    else:
        session.add(PresenceRecord(
            user_id=user.id, target_kind=body.target_kind,
            target_id=body.target_id, last_heartbeat=now,
        ))
    await session.flush()

    # Cleanup expired records (any older than 5 min) — quick GC each call
    cutoff = now - timedelta(minutes=5)
    await session.execute(
        delete(PresenceRecord).where(PresenceRecord.last_heartbeat < cutoff)
    )

    # Return live viewers
    return await viewers(body.target_kind, body.target_id, session, user)


@router.get("", response_model=PresenceOut)
async def viewers(
    target_kind: str,
    target_id: uuid.UUID,
    session: DBSession,
    _: CurrentUser,
) -> PresenceOut:
    cutoff = datetime.now(timezone.utc) - ACTIVE_WINDOW
    res = await session.execute(
        select(PresenceRecord, User)
        .join(User, User.id == PresenceRecord.user_id)
        .where(PresenceRecord.target_kind == target_kind)
        .where(PresenceRecord.target_id == target_id)
        .where(PresenceRecord.last_heartbeat >= cutoff)
    )
    out: list[PresenceUser] = []
    now = datetime.now(timezone.utc)
    for pr, u in res.all():
        # last_heartbeat may come back naive in some drivers; coerce to UTC
        lh = pr.last_heartbeat
        if lh.tzinfo is None:
            lh = lh.replace(tzinfo=timezone.utc)
        secs = max(0, int((now - lh).total_seconds()))
        out.append(PresenceUser(
            user_id=u.id, email=u.email, display_name=u.display_name,
            seconds_since_heartbeat=secs,
        ))
    return PresenceOut(target_kind=target_kind, target_id=target_id, viewers=out)
