"""Hearing schedule + roster."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Hearing
from ..services.audit import log_event

router = APIRouter(prefix="/hearings", tags=["hearings"])


class HearingIn(BaseModel):
    case_id: uuid.UUID
    title: str
    hearing_date: Optional[date] = None
    location: Optional[str] = None
    presiding_alj: Optional[str] = None
    witness_lineup: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    notes: Optional[str] = None
    status: str = "scheduled"


class HearingOut(HearingIn):
    id: uuid.UUID


@router.get("", response_model=list[HearingOut])
async def list_hearings(
    session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)
) -> list[HearingOut]:
    res = await session.execute(
        select(Hearing).where(Hearing.case_id == case_id).order_by(Hearing.hearing_date.asc().nullslast())
    )
    return [HearingOut(**{**h.__dict__, "id": h.id}) for h in res.scalars().all()]


@router.post("", response_model=HearingOut, status_code=201)
async def create_hearing(
    body: HearingIn, session: DBSession, user: CurrentUser
) -> HearingOut:
    h = Hearing(**body.model_dump(mode="json"))
    session.add(h)
    await session.flush()
    await log_event(
        session, actor=user, verb="hearing.scheduled", target_kind="hearing",
        target_id=h.id, case_id=body.case_id,
        payload={"date": body.hearing_date.isoformat() if body.hearing_date else None},
    )
    return HearingOut(**{**h.__dict__, "id": h.id})


@router.patch("/{hearing_id}", response_model=HearingOut)
async def update_hearing(
    hearing_id: uuid.UUID, body: HearingIn, session: DBSession, user: CurrentUser
) -> HearingOut:
    res = await session.execute(select(Hearing).where(Hearing.id == hearing_id))
    h = res.scalar_one_or_none()
    if not h:
        raise HTTPException(404, "hearing not found")
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(h, k, v)
    await session.flush()
    await log_event(
        session, actor=user, verb="hearing.updated", target_kind="hearing",
        target_id=h.id, case_id=h.case_id, payload={"status": body.status},
    )
    return HearingOut(**{**h.__dict__, "id": h.id})
