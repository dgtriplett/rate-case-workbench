"""Rebuttal workbench — intervenor positions + the rebuttal testimony that
addresses them. The endpoints in this file expose the per-case list of
positions and let a user link a rebuttal testimony to one or more positions.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import IntervenorPosition, Testimony
from ..services.audit import log_event

router = APIRouter(prefix="/intervenor-positions", tags=["rebuttal"])


class IntervenorPositionIn(BaseModel):
    case_id: uuid.UUID
    intervenor: str
    intervenor_kind: Optional[str] = None
    topic: str
    position_text: str
    source_citation: Optional[str] = None
    proposed_adjustment: Optional[str] = None
    impact_amount_m: Optional[float] = None
    filed_date: Optional[date] = None


class IntervenorPositionOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    intervenor: str
    intervenor_kind: Optional[str]
    topic: str
    position_text: str
    source_citation: Optional[str]
    proposed_adjustment: Optional[str]
    impact_amount_m: Optional[float]
    filed_date: Optional[date]
    status: str
    rebutted_by_testimony_id: Optional[uuid.UUID]


class LinkRebuttal(BaseModel):
    testimony_id: uuid.UUID


@router.get("", response_model=list[IntervenorPositionOut])
async def list_positions(
    session: DBSession,
    _: CurrentUser,
    case_id: uuid.UUID = Query(...),
    status: Optional[str] = Query(default=None),
) -> list[IntervenorPositionOut]:
    q = select(IntervenorPosition).where(IntervenorPosition.case_id == case_id)
    if status:
        q = q.where(IntervenorPosition.status == status)
    q = q.order_by(IntervenorPosition.filed_date.desc().nullslast(), IntervenorPosition.topic)
    rows = (await session.execute(q)).scalars().all()
    return [
        IntervenorPositionOut(
            id=r.id, case_id=r.case_id, intervenor=r.intervenor,
            intervenor_kind=r.intervenor_kind, topic=r.topic,
            position_text=r.position_text, source_citation=r.source_citation,
            proposed_adjustment=r.proposed_adjustment, impact_amount_m=r.impact_amount_m,
            filed_date=r.filed_date, status=r.status,
            rebutted_by_testimony_id=r.rebutted_by_testimony_id,
        )
        for r in rows
    ]


@router.post("", response_model=IntervenorPositionOut, status_code=201)
async def create_position(
    body: IntervenorPositionIn, session: DBSession, user: CurrentUser
) -> IntervenorPositionOut:
    p = IntervenorPosition(
        case_id=body.case_id, intervenor=body.intervenor,
        intervenor_kind=body.intervenor_kind, topic=body.topic,
        position_text=body.position_text, source_citation=body.source_citation,
        proposed_adjustment=body.proposed_adjustment,
        impact_amount_m=body.impact_amount_m, filed_date=body.filed_date,
    )
    session.add(p)
    await session.flush()
    await log_event(
        session, actor=user, verb="position.created", target_kind="intervenor_position",
        target_id=p.id, case_id=p.case_id,
        payload={"intervenor": body.intervenor, "topic": body.topic},
    )
    return IntervenorPositionOut(
        id=p.id, case_id=p.case_id, intervenor=p.intervenor,
        intervenor_kind=p.intervenor_kind, topic=p.topic,
        position_text=p.position_text, source_citation=p.source_citation,
        proposed_adjustment=p.proposed_adjustment, impact_amount_m=p.impact_amount_m,
        filed_date=p.filed_date, status=p.status,
        rebutted_by_testimony_id=p.rebutted_by_testimony_id,
    )


@router.post("/{position_id}/link-rebuttal", response_model=IntervenorPositionOut)
async def link_rebuttal(
    position_id: uuid.UUID, body: LinkRebuttal, session: DBSession, user: CurrentUser
) -> IntervenorPositionOut:
    pres = await session.execute(select(IntervenorPosition).where(IntervenorPosition.id == position_id))
    p = pres.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "position not found")
    tres = await session.execute(select(Testimony).where(Testimony.id == body.testimony_id))
    t = tres.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "testimony not found")
    p.rebutted_by_testimony_id = t.id
    p.status = "rebutted"
    # Also reflect the link from the testimony side (rebuts_position_ids array)
    pid_str = str(p.id)
    if pid_str not in (t.rebuts_position_ids or []):
        t.rebuts_position_ids = list(t.rebuts_position_ids or []) + [pid_str]
    await log_event(
        session, actor=user, verb="position.rebuttal_linked",
        target_kind="intervenor_position", target_id=p.id, case_id=p.case_id,
        payload={"testimony_id": str(t.id), "topic": p.topic},
    )
    await session.flush()
    return IntervenorPositionOut(
        id=p.id, case_id=p.case_id, intervenor=p.intervenor,
        intervenor_kind=p.intervenor_kind, topic=p.topic,
        position_text=p.position_text, source_citation=p.source_citation,
        proposed_adjustment=p.proposed_adjustment, impact_amount_m=p.impact_amount_m,
        filed_date=p.filed_date, status=p.status,
        rebutted_by_testimony_id=p.rebutted_by_testimony_id,
    )
