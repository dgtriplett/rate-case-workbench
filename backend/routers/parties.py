"""Stakeholder registry — intervening parties + counsel."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Party
from ..services.audit import log_event

router = APIRouter(prefix="/parties", tags=["parties"])


class PartyIn(BaseModel):
    case_id: uuid.UUID
    name: str
    kind: str = "other"
    counsel_name: Optional[str] = None
    counsel_email: Optional[str] = None
    counsel_firm: Optional[str] = None
    intervention_date: Optional[date] = None
    notes: Optional[str] = None
    is_active: bool = True


class PartyOut(PartyIn):
    id: uuid.UUID


@router.get("", response_model=list[PartyOut])
async def list_parties(session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)) -> list[PartyOut]:
    res = await session.execute(
        select(Party).where(Party.case_id == case_id).order_by(Party.intervention_date.asc().nullsfirst(), Party.name)
    )
    return [PartyOut(id=r.id, **{k: getattr(r, k) for k in PartyIn.model_fields}) for r in res.scalars().all()]


@router.post("", response_model=PartyOut, status_code=201)
async def create_party(body: PartyIn, session: DBSession, user: CurrentUser) -> PartyOut:
    r = Party(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="party.intervened", target_kind="party",
        target_id=r.id, case_id=body.case_id, payload={"name": body.name, "kind": body.kind},
    )
    return PartyOut(id=r.id, **{k: getattr(r, k) for k in PartyIn.model_fields})


@router.patch("/{party_id}", response_model=PartyOut)
async def update_party(party_id: uuid.UUID, body: PartyIn, session: DBSession, _: CurrentUser) -> PartyOut:
    res = await session.execute(select(Party).where(Party.id == party_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "party not found")
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(r, k, v)
    await session.flush()
    return PartyOut(id=r.id, **{k: getattr(r, k) for k in PartyIn.model_fields})


@router.delete("/{party_id}")
async def delete_party(party_id: uuid.UUID, session: DBSession, _: CurrentUser) -> dict:
    res = await session.execute(select(Party).where(Party.id == party_id))
    r = res.scalar_one_or_none()
    if r:
        await session.delete(r)
        await session.flush()
    return {"deleted": True}
