from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case, CasePhase, PhaseStatus, PhaseType
from ..schemas import CaseCreate, CaseOut, PhaseOut
from ..services.audit import log_event

router = APIRouter(prefix="/cases", tags=["cases"])

DEFAULT_PHASE_SEQUENCE: list[PhaseType] = [
    PhaseType.pre_filing,
    PhaseType.filing,
    PhaseType.discovery,
    PhaseType.direct_testimony,
    PhaseType.rebuttal,
    PhaseType.surrebuttal,
    PhaseType.hearing,
    PhaseType.post_hearing_briefs,
    PhaseType.order,
    PhaseType.compliance,
]


@router.get("", response_model=list[CaseOut])
async def list_cases(session: DBSession, _: CurrentUser) -> list[CaseOut]:
    res = await session.execute(select(Case).order_by(Case.filed_date.desc().nullslast()))
    return [CaseOut.model_validate(c) for c in res.scalars().all()]


@router.post("", response_model=CaseOut, status_code=201)
async def create_case(body: CaseCreate, session: DBSession, user: CurrentUser) -> CaseOut:
    case = Case(
        name=body.name,
        docket_number=body.docket_number,
        jurisdiction=body.jurisdiction,
        commission=body.commission,
        utility_name=body.utility_name,
        case_type=body.case_type,
        description=body.description,
        filed_date=body.filed_date,
        target_decision_date=body.target_decision_date,
        primary_case_manager_id=user.id,
        created_by=user.id,
    )
    session.add(case)
    await session.flush()
    for i, pt in enumerate(DEFAULT_PHASE_SEQUENCE, start=1):
        session.add(CasePhase(case_id=case.id, phase_type=pt, sequence=i, status=PhaseStatus.not_started))
    await log_event(
        session,
        actor=user,
        verb="case.created",
        target_kind="case",
        target_id=case.id,
        case_id=case.id,
        payload={"docket": case.docket_number, "name": case.name},
    )
    await session.flush()
    return CaseOut.model_validate(case)


@router.get("/{case_id}", response_model=CaseOut)
async def get_case(case_id: uuid.UUID, session: DBSession, _: CurrentUser) -> CaseOut:
    res = await session.execute(select(Case).where(Case.id == case_id))
    case = res.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")
    return CaseOut.model_validate(case)


@router.get("/{case_id}/phases", response_model=list[PhaseOut])
async def list_phases(case_id: uuid.UUID, session: DBSession, _: CurrentUser) -> list[PhaseOut]:
    res = await session.execute(
        select(CasePhase).where(CasePhase.case_id == case_id).order_by(CasePhase.sequence)
    )
    return [PhaseOut.model_validate(p) for p in res.scalars().all()]
