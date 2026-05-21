"""Commission order / final-decision endpoints."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import CommissionOrder
from ..services.audit import log_event

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderIn(BaseModel):
    case_id: uuid.UUID
    order_number: Optional[str] = None
    issued_date: Optional[date] = None
    effective_date: Optional[date] = None
    authorized_revenue_increase_m: Optional[float] = None
    authorized_roe_pct: Optional[float] = None
    authorized_equity_pct: Optional[float] = None
    capex_approved_m: Optional[float] = None
    summary: Optional[str] = None
    full_text_document_id: Optional[uuid.UUID] = None
    compliance_filings_due: Optional[date] = None


class OrderOut(OrderIn):
    id: uuid.UUID


@router.get("/by-case/{case_id}", response_model=Optional[OrderOut])
async def get_for_case(case_id: uuid.UUID, session: DBSession, _: CurrentUser) -> Optional[OrderOut]:
    res = await session.execute(select(CommissionOrder).where(CommissionOrder.case_id == case_id))
    o = res.scalar_one_or_none()
    if not o:
        return None
    return OrderOut(**{**o.__dict__, "id": o.id})


@router.put("/by-case/{case_id}", response_model=OrderOut)
async def upsert_order(
    case_id: uuid.UUID, body: OrderIn, session: DBSession, user: CurrentUser
) -> OrderOut:
    if body.case_id != case_id:
        raise HTTPException(400, "case_id mismatch")
    res = await session.execute(select(CommissionOrder).where(CommissionOrder.case_id == case_id))
    o = res.scalar_one_or_none()
    if not o:
        o = CommissionOrder(**body.model_dump(mode="json"))
        session.add(o)
        verb = "order.created"
    else:
        for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
            setattr(o, k, v)
        verb = "order.updated"
    await session.flush()
    await log_event(
        session, actor=user, verb=verb, target_kind="order",
        target_id=o.id, case_id=case_id,
        payload={"roe": body.authorized_roe_pct, "rev_increase_m": body.authorized_revenue_increase_m},
    )
    return OrderOut(**{**o.__dict__, "id": o.id})
