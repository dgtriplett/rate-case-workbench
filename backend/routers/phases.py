from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import CasePhase, PhaseStatus
from ..schemas import PhaseOut, PhaseUpdate
from ..services.audit import log_event

router = APIRouter(prefix="/phases", tags=["phases"])


@router.get("/{phase_id}", response_model=PhaseOut)
async def get_phase(phase_id: uuid.UUID, session: DBSession, _: CurrentUser) -> PhaseOut:
    res = await session.execute(select(CasePhase).where(CasePhase.id == phase_id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "phase not found")
    return PhaseOut.model_validate(p)


@router.patch("/{phase_id}", response_model=PhaseOut)
async def update_phase(
    phase_id: uuid.UUID, body: PhaseUpdate, session: DBSession, user: CurrentUser
) -> PhaseOut:
    res = await session.execute(select(CasePhase).where(CasePhase.id == phase_id))
    p = res.scalar_one_or_none()
    if not p:
        raise HTTPException(404, "phase not found")
    if body.status is not None:
        p.status = PhaseStatus(body.status)
    if body.start_date is not None:
        p.start_date = body.start_date
    if body.end_date is not None:
        p.end_date = body.end_date
    if body.deadline_date is not None:
        p.deadline_date = body.deadline_date
    if body.notes is not None:
        p.notes = body.notes
    await log_event(
        session,
        actor=user,
        verb="phase.updated",
        target_kind="phase",
        target_id=p.id,
        case_id=p.case_id,
        payload=body.model_dump(exclude_none=True, mode="json"),
    )
    await session.flush()
    return PhaseOut.model_validate(p)
