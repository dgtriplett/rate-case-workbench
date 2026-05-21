from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import DataRequest, DRStatus
from ..schemas import DataRequestAssign, DataRequestCreate, DataRequestOut
from ..services.audit import log_event

router = APIRouter(prefix="/data-requests", tags=["data-requests"])


@router.get("", response_model=list[DataRequestOut])
async def list_drs(
    session: DBSession,
    _: CurrentUser,
    case_id: Optional[uuid.UUID] = Query(default=None),
    status: Optional[str] = Query(default=None),
    assigned_witness_id: Optional[uuid.UUID] = Query(default=None),
) -> list[DataRequestOut]:
    q = select(DataRequest)
    if case_id:
        q = q.where(DataRequest.case_id == case_id)
    if status:
        q = q.where(DataRequest.status == DRStatus(status))
    if assigned_witness_id:
        q = q.where(DataRequest.assigned_witness_id == assigned_witness_id)
    q = q.order_by(DataRequest.due_date.asc(), DataRequest.created_at.desc()).limit(2000)
    res = await session.execute(q)
    return [DataRequestOut.model_validate(d) for d in res.scalars().all()]


@router.post("", response_model=DataRequestOut, status_code=201)
async def create_dr(body: DataRequestCreate, session: DBSession, user: CurrentUser) -> DataRequestOut:
    dr = DataRequest(
        case_id=body.case_id,
        phase_id=body.phase_id,
        dr_number=body.dr_number,
        requester=body.requester,
        requester_kind=body.requester_kind,
        issued_date=body.issued_date,
        due_date=body.due_date,
        subject=body.subject,
        body=body.body,
        priority=body.priority,
        topic_tags=body.topic_tags,
    )
    session.add(dr)
    await session.flush()
    await log_event(
        session,
        actor=user,
        verb="data_request.created",
        target_kind="data_request",
        target_id=dr.id,
        case_id=dr.case_id,
        payload={"dr_number": dr.dr_number, "requester": dr.requester},
    )
    return DataRequestOut.model_validate(dr)


@router.get("/{dr_id}", response_model=DataRequestOut)
async def get_dr(dr_id: uuid.UUID, session: DBSession, _: CurrentUser) -> DataRequestOut:
    res = await session.execute(select(DataRequest).where(DataRequest.id == dr_id))
    dr = res.scalar_one_or_none()
    if not dr:
        raise HTTPException(404, "DR not found")
    return DataRequestOut.model_validate(dr)


@router.post("/{dr_id}/assign", response_model=DataRequestOut)
async def assign_dr(
    dr_id: uuid.UUID, body: DataRequestAssign, session: DBSession, user: CurrentUser
) -> DataRequestOut:
    res = await session.execute(select(DataRequest).where(DataRequest.id == dr_id))
    dr = res.scalar_one_or_none()
    if not dr:
        raise HTTPException(404, "DR not found")
    if body.assigned_witness_id is not None:
        dr.assigned_witness_id = body.assigned_witness_id
    if body.assigned_reviewer_id is not None:
        dr.assigned_reviewer_id = body.assigned_reviewer_id
    if dr.status == DRStatus.new and dr.assigned_witness_id:
        dr.status = DRStatus.assigned
    await log_event(
        session,
        actor=user,
        verb="data_request.assigned",
        target_kind="data_request",
        target_id=dr.id,
        case_id=dr.case_id,
        payload={
            "witness_id": str(dr.assigned_witness_id) if dr.assigned_witness_id else None,
            "reviewer_id": str(dr.assigned_reviewer_id) if dr.assigned_reviewer_id else None,
        },
    )
    return DataRequestOut.model_validate(dr)
