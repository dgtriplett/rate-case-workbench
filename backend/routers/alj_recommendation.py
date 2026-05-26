"""ALJ recommendations — recommended decision before the final commission order."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import ALJRecommendation, CommissionOrder
from ..services.audit import log_event

router = APIRouter(prefix="/alj-recommendation", tags=["alj-recommendation"])


class RecIn(BaseModel):
    case_id: uuid.UUID
    alj_name: Optional[str] = None
    issued_date: Optional[date] = None
    recommended_revenue_increase_m: Optional[float] = None
    recommended_roe_pct: Optional[float] = None
    recommended_equity_pct: Optional[float] = None
    capex_recommended_m: Optional[float] = None
    summary: Optional[str] = None
    positions_adopted: list[str] = Field(default_factory=list)
    positions_rejected: list[str] = Field(default_factory=list)
    document_id: Optional[uuid.UUID] = None


class RecOut(RecIn):
    id: uuid.UUID


class CompareOut(BaseModel):
    requested: dict
    alj_recommended: dict
    commission_ordered: dict


@router.get("/by-case/{case_id}", response_model=Optional[RecOut])
async def get_for_case(case_id: uuid.UUID, session: DBSession, _: CurrentUser) -> Optional[RecOut]:
    res = await session.execute(select(ALJRecommendation).where(ALJRecommendation.case_id == case_id))
    r = res.scalar_one_or_none()
    if not r:
        return None
    return RecOut(id=r.id, **{k: getattr(r, k) for k in RecIn.model_fields})


@router.put("/by-case/{case_id}", response_model=RecOut)
async def upsert(
    case_id: uuid.UUID, body: RecIn, session: DBSession, user: CurrentUser
) -> RecOut:
    if body.case_id != case_id:
        raise HTTPException(400, "case_id mismatch")
    res = await session.execute(select(ALJRecommendation).where(ALJRecommendation.case_id == case_id))
    r = res.scalar_one_or_none()
    if r is None:
        r = ALJRecommendation(**body.model_dump(mode="json"))
        session.add(r)
        verb = "alj_recommendation.created"
    else:
        for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
            setattr(r, k, v)
        verb = "alj_recommendation.updated"
    await session.flush()
    await log_event(
        session, actor=user, verb=verb, target_kind="alj_recommendation",
        target_id=r.id, case_id=case_id,
        payload={"roe": body.recommended_roe_pct, "rev_m": body.recommended_revenue_increase_m},
    )
    return RecOut(id=r.id, **{k: getattr(r, k) for k in RecIn.model_fields})


@router.get("/compare/{case_id}", response_model=CompareOut)
async def compare(case_id: uuid.UUID, session: DBSession, _: CurrentUser) -> CompareOut:
    """Three-way comparison: Company request → ALJ recommended → Commission ordered."""
    rec = (await session.execute(
        select(ALJRecommendation).where(ALJRecommendation.case_id == case_id)
    )).scalar_one_or_none()
    order = (await session.execute(
        select(CommissionOrder).where(CommissionOrder.case_id == case_id)
    )).scalar_one_or_none()

    return CompareOut(
        requested={"label": "Company request", "roe_pct": None, "revenue_increase_m": None, "capex_m": None, "equity_pct": None},
        alj_recommended={
            "label": "ALJ recommended",
            "roe_pct": rec.recommended_roe_pct if rec else None,
            "revenue_increase_m": rec.recommended_revenue_increase_m if rec else None,
            "capex_m": rec.capex_recommended_m if rec else None,
            "equity_pct": rec.recommended_equity_pct if rec else None,
        },
        commission_ordered={
            "label": "Commission ordered",
            "roe_pct": order.authorized_roe_pct if order else None,
            "revenue_increase_m": order.authorized_revenue_increase_m if order else None,
            "capex_m": order.capex_approved_m if order else None,
            "equity_pct": order.authorized_equity_pct if order else None,
        },
    )
