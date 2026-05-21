from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import ResponseStatus, Testimony, TestimonyKind
from ..schemas import TestimonyCreate, TestimonyOut
from ..services.audit import log_event

router = APIRouter(prefix="/testimony", tags=["testimony"])


class TestimonyUpdate(BaseModel):
    draft_text: Optional[str] = None
    final_text: Optional[str] = None
    status: Optional[str] = None


@router.get("", response_model=list[TestimonyOut])
async def list_testimony(
    session: DBSession,
    _: CurrentUser,
    case_id: Optional[uuid.UUID] = Query(default=None),
) -> list[TestimonyOut]:
    q = select(Testimony)
    if case_id:
        q = q.where(Testimony.case_id == case_id)
    q = q.order_by(Testimony.created_at.desc())
    res = await session.execute(q)
    return [TestimonyOut.model_validate(t) for t in res.scalars().all()]


_KIND_TO_PHASE = {
    "direct": "direct_testimony",
    "rebuttal": "rebuttal",
    "surrebuttal": "surrebuttal",
    "initial_brief": "post_hearing_briefs",
    "reply_brief": "post_hearing_briefs",
}


@router.post("", response_model=TestimonyOut, status_code=201)
async def create_testimony(
    body: TestimonyCreate, session: DBSession, user: CurrentUser
) -> TestimonyOut:
    from sqlalchemy import text as _text

    t = Testimony(
        case_id=body.case_id,
        phase_id=body.phase_id,
        witness_id=body.witness_id,
        kind=TestimonyKind(body.kind),
        title=body.title,
        draft_text=body.draft_text,
    )
    session.add(t)
    await session.flush()

    # Auto-advance the corresponding phase to in_progress and tie the
    # testimony row to that phase so it appears on the Phase Board.
    phase_name = _KIND_TO_PHASE.get(body.kind)
    if phase_name:
        await session.execute(
            _text(
                "UPDATE case_phases SET status = 'in_progress'::phase_status "
                "WHERE case_id = :c AND phase_type = :p AND status = 'not_started'::phase_status"
            ),
            {"c": str(body.case_id), "p": phase_name},
        )
        if t.phase_id is None:
            row = (await session.execute(
                _text(
                    "SELECT id FROM case_phases WHERE case_id = :c AND phase_type = :p"
                ),
                {"c": str(body.case_id), "p": phase_name},
            )).first()
            if row:
                t.phase_id = row[0]

    await log_event(
        session, actor=user, verb="testimony.created", target_kind="testimony",
        target_id=t.id, case_id=t.case_id, payload={"kind": body.kind, "title": body.title},
    )
    await session.flush()
    return TestimonyOut.model_validate(t)


@router.get("/{testimony_id}", response_model=TestimonyOut)
async def get_testimony(
    testimony_id: uuid.UUID, session: DBSession, _: CurrentUser
) -> TestimonyOut:
    res = await session.execute(select(Testimony).where(Testimony.id == testimony_id))
    t = res.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "testimony not found")
    return TestimonyOut.model_validate(t)


@router.patch("/{testimony_id}", response_model=TestimonyOut)
async def update_testimony(
    testimony_id: uuid.UUID, body: TestimonyUpdate, session: DBSession, user: CurrentUser
) -> TestimonyOut:
    res = await session.execute(select(Testimony).where(Testimony.id == testimony_id))
    t = res.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "testimony not found")
    if body.draft_text is not None:
        t.draft_text = body.draft_text
    if body.final_text is not None:
        t.final_text = body.final_text
    if body.status is not None:
        t.status = ResponseStatus(body.status)
        if t.status == ResponseStatus.filed and t.filed_at is None:
            t.filed_at = datetime.now(timezone.utc)
    await log_event(
        session, actor=user, verb="testimony.updated", target_kind="testimony",
        target_id=t.id, case_id=t.case_id, payload=body.model_dump(exclude_none=True),
    )
    await session.flush()
    return TestimonyOut.model_validate(t)


async def _load(session, tid: uuid.UUID) -> Testimony:
    res = await session.execute(select(Testimony).where(Testimony.id == tid))
    t = res.scalar_one_or_none()
    if not t:
        raise HTTPException(404, "testimony not found")
    return t


@router.post("/{testimony_id}/submit", response_model=TestimonyOut)
async def submit_for_review(testimony_id: uuid.UUID, session: DBSession, user: CurrentUser) -> TestimonyOut:
    t = await _load(session, testimony_id)
    t.status = ResponseStatus.in_review
    await log_event(session, actor=user, verb="testimony.submitted", target_kind="testimony", target_id=t.id, case_id=t.case_id)
    await session.flush()
    return TestimonyOut.model_validate(t)


@router.post("/{testimony_id}/approve", response_model=TestimonyOut)
async def approve_testimony(testimony_id: uuid.UUID, session: DBSession, user: CurrentUser) -> TestimonyOut:
    t = await _load(session, testimony_id)
    t.status = ResponseStatus.approved
    t.final_text = t.final_text or t.draft_text
    await log_event(session, actor=user, verb="testimony.approved", target_kind="testimony", target_id=t.id, case_id=t.case_id)
    await session.flush()
    return TestimonyOut.model_validate(t)


@router.post("/{testimony_id}/file", response_model=TestimonyOut)
async def file_testimony(testimony_id: uuid.UUID, session: DBSession, user: CurrentUser) -> TestimonyOut:
    t = await _load(session, testimony_id)
    if t.status != ResponseStatus.approved:
        raise HTTPException(400, "only approved testimony can be filed")
    t.status = ResponseStatus.filed
    t.filed_at = datetime.now(timezone.utc)
    await log_event(session, actor=user, verb="testimony.filed", target_kind="testimony", target_id=t.id, case_id=t.case_id)
    await session.flush()
    return TestimonyOut.model_validate(t)
