from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from sqlalchemy import select, update

from ..deps import CurrentUser, DBSession
from ..models import DataRequest, DRStatus, Response, ResponseCitation, ResponseStatus
from ..schemas import ApproveIn, CitationOut, ResponseDraftIn, ResponseOut
from ..services.audit import log_event

router = APIRouter(tags=["responses"])


def _to_out(r: Response) -> ResponseOut:
    return ResponseOut(
        id=r.id,
        data_request_id=r.data_request_id,
        version=r.version,
        is_current=r.is_current,
        draft_text=r.draft_text,
        final_text=r.final_text,
        agent_trace_id=r.agent_trace_id,
        model_version=r.model_version,
        privilege_flags=list(r.privilege_flags or []),
        status=r.status.value,
        approved_by=r.approved_by,
        approved_at=r.approved_at,
        filed_at=r.filed_at,
        created_at=r.created_at,
        updated_at=r.updated_at,
        citations=[CitationOut.model_validate(c) for c in (r.citations or [])],
    )


@router.get("/data-requests/{dr_id}/response", response_model=Optional[ResponseOut])
async def current_response(dr_id: uuid.UUID, session: DBSession, _: CurrentUser) -> Optional[ResponseOut]:
    res = await session.execute(
        select(Response).where(Response.data_request_id == dr_id, Response.is_current == True)  # noqa: E712
    )
    r = res.scalar_one_or_none()
    return _to_out(r) if r else None


@router.post("/data-requests/{dr_id}/responses", response_model=ResponseOut, status_code=201)
async def save_draft(
    dr_id: uuid.UUID, body: ResponseDraftIn, session: DBSession, user: CurrentUser
) -> ResponseOut:
    dres = await session.execute(select(DataRequest).where(DataRequest.id == dr_id))
    dr = dres.scalar_one_or_none()
    if not dr:
        raise HTTPException(404, "DR not found")

    res = await session.execute(
        select(Response).where(Response.data_request_id == dr_id, Response.is_current == True)  # noqa: E712
    )
    current = res.scalar_one_or_none()
    next_version = (current.version + 1) if current else 1
    if current:
        await session.execute(
            update(Response).where(Response.id == current.id).values(is_current=False)
        )
    new_r = Response(
        data_request_id=dr_id,
        version=next_version,
        is_current=True,
        draft_text=body.draft_text,
        drafted_by=user.id,
        agent_trace_id=body.agent_trace_id,
        agent_reasoning=body.agent_reasoning,
        model_version=body.model_version,
        privilege_flags=body.privilege_flags or [],
        status=ResponseStatus.draft,
    )
    session.add(new_r)
    await session.flush()

    for c in body.citations or []:
        session.add(
            ResponseCitation(
                response_id=new_r.id,
                source_type=c.source_type,
                source_id=c.source_id,
                label=c.label,
                snippet=c.snippet,
                page=c.page,
                span_start=c.span_start,
                span_end=c.span_end,
            )
        )
    if dr.status in (DRStatus.new, DRStatus.assigned):
        dr.status = DRStatus.drafting
    await log_event(
        session,
        actor=user,
        verb="response.draft_saved",
        target_kind="response",
        target_id=new_r.id,
        case_id=dr.case_id,
        payload={"version": next_version, "dr_id": str(dr_id)},
    )
    await session.flush()

    fres = await session.execute(select(Response).where(Response.id == new_r.id))
    return _to_out(fres.scalar_one())


@router.post("/responses/{response_id}/submit", response_model=ResponseOut)
async def submit_for_review(
    response_id: uuid.UUID, session: DBSession, user: CurrentUser
) -> ResponseOut:
    r = await _load_response(session, response_id)
    r.status = ResponseStatus.in_review
    dr = await _load_dr(session, r.data_request_id)
    dr.status = DRStatus.in_review
    await log_event(
        session, actor=user, verb="response.submitted", target_kind="response",
        target_id=r.id, case_id=dr.case_id, payload={"version": r.version},
    )
    await session.flush()
    return _to_out(r)


@router.post("/responses/{response_id}/approve", response_model=ResponseOut)
async def approve(
    response_id: uuid.UUID, body: ApproveIn, session: DBSession, user: CurrentUser
) -> ResponseOut:
    r = await _load_response(session, response_id)
    r.status = ResponseStatus.approved
    r.approved_by = user.id
    r.approved_at = datetime.now(timezone.utc)
    r.final_text = r.final_text or r.draft_text
    dr = await _load_dr(session, r.data_request_id)
    dr.status = DRStatus.approved
    await log_event(
        session, actor=user, verb="response.approved", target_kind="response",
        target_id=r.id, case_id=dr.case_id, payload={"comment": body.comment, "version": r.version},
    )
    # NOTE: memory_writer job picks this up via watermark on r.approved_at
    await session.flush()
    return _to_out(r)


@router.post("/responses/{response_id}/file", response_model=ResponseOut)
async def file_response(
    response_id: uuid.UUID, session: DBSession, user: CurrentUser
) -> ResponseOut:
    r = await _load_response(session, response_id)
    if r.status != ResponseStatus.approved:
        raise HTTPException(400, "Only approved responses can be filed")
    r.status = ResponseStatus.filed
    r.filed_at = datetime.now(timezone.utc)
    r.filed_by = user.id
    dr = await _load_dr(session, r.data_request_id)
    dr.status = DRStatus.filed
    await log_event(
        session, actor=user, verb="response.filed", target_kind="response",
        target_id=r.id, case_id=dr.case_id, payload={"version": r.version},
    )
    await session.flush()
    return _to_out(r)


@router.get("/responses/{response_id}", response_model=ResponseOut)
async def get_response(response_id: uuid.UUID, session: DBSession, _: CurrentUser) -> ResponseOut:
    r = await _load_response(session, response_id)
    return _to_out(r)


@router.get("/data-requests/{dr_id}/responses", response_model=list[ResponseOut])
async def response_history(dr_id: uuid.UUID, session: DBSession, _: CurrentUser) -> list[ResponseOut]:
    res = await session.execute(
        select(Response).where(Response.data_request_id == dr_id).order_by(Response.version.desc())
    )
    return [_to_out(r) for r in res.scalars().all()]


async def _load_response(session, response_id: uuid.UUID) -> Response:
    res = await session.execute(select(Response).where(Response.id == response_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "response not found")
    return r


async def _load_dr(session, dr_id: uuid.UUID) -> DataRequest:
    res = await session.execute(select(DataRequest).where(DataRequest.id == dr_id))
    dr = res.scalar_one_or_none()
    if not dr:
        raise HTTPException(404, "DR not found")
    return dr
