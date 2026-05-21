"""Admin-scoped case operations (list all, archive)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import Case, CaseStatus
from ...schemas import CaseOut
from ...services.audit import log_event

router = APIRouter(prefix="/cases", tags=["admin-cases"])


@router.get("", response_model=list[CaseOut])
async def list_all_cases(session: DBSession, _: RequireAdmin) -> list[CaseOut]:
    res = await session.execute(select(Case).order_by(Case.created_at.desc()))
    return [CaseOut.model_validate(c) for c in res.scalars().all()]


@router.post("/{case_id}/archive", response_model=CaseOut)
async def archive_case(case_id: uuid.UUID, session: DBSession, admin: RequireAdmin) -> CaseOut:
    res = await session.execute(select(Case).where(Case.id == case_id))
    case = res.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")
    case.status = CaseStatus.closed
    await log_event(
        session,
        actor=admin,
        verb="case.archived",
        target_kind="case",
        target_id=case.id,
        case_id=case.id,
    )
    await session.flush()
    return CaseOut.model_validate(case)
