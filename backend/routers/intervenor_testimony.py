"""Intervenor testimony — full opposing-party filings tracked as documents."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import IntervenorTestimony
from ..services.audit import log_event

router = APIRouter(prefix="/intervenor-testimony", tags=["intervenor-testimony"])


class InterTestIn(BaseModel):
    case_id: uuid.UUID
    party_id: Optional[uuid.UUID] = None
    witness_name: str
    witness_title: Optional[str] = None
    kind: str = "direct"
    title: str
    filed_date: Optional[date] = None
    document_id: Optional[uuid.UUID] = None
    topics: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class InterTestOut(InterTestIn):
    id: uuid.UUID


@router.get("", response_model=list[InterTestOut])
async def list_filings(
    session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)
) -> list[InterTestOut]:
    res = await session.execute(
        select(IntervenorTestimony).where(IntervenorTestimony.case_id == case_id).order_by(IntervenorTestimony.filed_date.desc().nullslast())
    )
    return [InterTestOut(id=r.id, **{k: getattr(r, k) for k in InterTestIn.model_fields}) for r in res.scalars()]


@router.post("", response_model=InterTestOut, status_code=201)
async def create(body: InterTestIn, session: DBSession, user: CurrentUser) -> InterTestOut:
    r = IntervenorTestimony(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="intervenor_testimony.logged",
        target_kind="intervenor_testimony", target_id=r.id, case_id=body.case_id,
        payload={"witness": body.witness_name, "kind": body.kind},
    )
    return InterTestOut(id=r.id, **{k: getattr(r, k) for k in InterTestIn.model_fields})


@router.patch("/{tid}", response_model=InterTestOut)
async def update(tid: uuid.UUID, body: InterTestIn, session: DBSession, _: CurrentUser) -> InterTestOut:
    res = await session.execute(select(IntervenorTestimony).where(IntervenorTestimony.id == tid))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "not found")
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(r, k, v)
    await session.flush()
    return InterTestOut(id=r.id, **{k: getattr(r, k) for k in InterTestIn.model_fields})


@router.delete("/{tid}")
async def delete(tid: uuid.UUID, session: DBSession, _: CurrentUser) -> dict:
    res = await session.execute(select(IntervenorTestimony).where(IntervenorTestimony.id == tid))
    r = res.scalar_one_or_none()
    if r:
        await session.delete(r)
        await session.flush()
    return {"deleted": True}
