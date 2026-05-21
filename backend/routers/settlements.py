"""Settlement negotiations."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Settlement
from ..services.audit import log_event

router = APIRouter(prefix="/settlements", tags=["settlements"])


class SettlementIn(BaseModel):
    case_id: uuid.UUID
    summary: str
    parties: list[str] = Field(default_factory=list)
    proposed_revenue_increase_m: Optional[float] = None
    proposed_roe_pct: Optional[float] = None
    status: str = "proposed"
    proposed_date: Optional[date] = None
    decision_date: Optional[date] = None
    full_text: Optional[str] = None


class SettlementOut(SettlementIn):
    id: uuid.UUID


@router.get("", response_model=list[SettlementOut])
async def list_settlements(
    session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)
) -> list[SettlementOut]:
    res = await session.execute(
        select(Settlement).where(Settlement.case_id == case_id).order_by(Settlement.proposed_date.desc().nullslast())
    )
    return [SettlementOut(**{**s.__dict__, "id": s.id}) for s in res.scalars().all()]


@router.post("", response_model=SettlementOut, status_code=201)
async def create_settlement(
    body: SettlementIn, session: DBSession, user: CurrentUser
) -> SettlementOut:
    s = Settlement(**body.model_dump(mode="json"))
    session.add(s)
    await session.flush()
    await log_event(
        session, actor=user, verb="settlement.created", target_kind="settlement",
        target_id=s.id, case_id=body.case_id,
        payload={"status": body.status, "rev_m": body.proposed_revenue_increase_m},
    )
    return SettlementOut(**{**s.__dict__, "id": s.id})


@router.patch("/{settlement_id}", response_model=SettlementOut)
async def update_settlement(
    settlement_id: uuid.UUID, body: SettlementIn, session: DBSession, user: CurrentUser
) -> SettlementOut:
    res = await session.execute(select(Settlement).where(Settlement.id == settlement_id))
    s = res.scalar_one_or_none()
    if not s:
        raise HTTPException(404, "settlement not found")
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(s, k, v)
    await session.flush()
    await log_event(
        session, actor=user, verb="settlement.updated", target_kind="settlement",
        target_id=s.id, case_id=s.case_id, payload={"status": body.status},
    )
    return SettlementOut(**{**s.__dict__, "id": s.id})
