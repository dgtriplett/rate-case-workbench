"""Public notices — required pre-filing notification with templated draft."""
from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case, PublicNotice
from ..services.audit import log_event
from ..services.llm import chat as llm_chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/public-notices", tags=["public-notices"])


class NoticeIn(BaseModel):
    case_id: uuid.UUID
    title: str
    body: str
    channels: list[str] = Field(default_factory=list)
    publication_date: Optional[date] = None
    status: str = "draft"


class NoticeOut(NoticeIn):
    id: uuid.UUID


@router.get("", response_model=list[NoticeOut])
async def list_notices(session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)) -> list[NoticeOut]:
    res = await session.execute(
        select(PublicNotice).where(PublicNotice.case_id == case_id).order_by(PublicNotice.publication_date.desc().nullslast())
    )
    return [NoticeOut(id=r.id, **{k: getattr(r, k) for k in NoticeIn.model_fields}) for r in res.scalars()]


@router.post("", response_model=NoticeOut, status_code=201)
async def create(body: NoticeIn, session: DBSession, user: CurrentUser) -> NoticeOut:
    r = PublicNotice(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="public_notice.created",
        target_kind="public_notice", target_id=r.id, case_id=body.case_id,
        payload={"channels": body.channels},
    )
    return NoticeOut(id=r.id, **{k: getattr(r, k) for k in NoticeIn.model_fields})


@router.patch("/{nid}", response_model=NoticeOut)
async def update(nid: uuid.UUID, body: NoticeIn, session: DBSession, _: CurrentUser) -> NoticeOut:
    res = await session.execute(select(PublicNotice).where(PublicNotice.id == nid))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "not found")
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(r, k, v)
    await session.flush()
    return NoticeOut(id=r.id, **{k: getattr(r, k) for k in NoticeIn.model_fields})


@router.post("/draft/{case_id}", response_model=NoticeOut)
async def draft_notice(case_id: uuid.UUID, session: DBSession, user: CurrentUser) -> NoticeOut:
    """Generate a public notice draft from the case context (utility, docket,
    jurisdiction, target filing date)."""
    cres = await session.execute(select(Case).where(Case.id == case_id))
    case = cres.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")
    prompt = (
        "Draft a Public Notice for a utility rate case filing. The text must "
        "be one continuous paragraph suitable for newspaper publication and "
        "include: (1) utility name, (2) docket number, (3) commission name, "
        "(4) general nature of the relief sought ('to increase rates and "
        "charges'), (5) where customers can review the application, (6) how "
        "and by when to file an intervention or comment. Be formal but plain-"
        "language. Keep under 200 words.\n\n"
        f"UTILITY: {case.utility_name}\nDOCKET: {case.docket_number}\n"
        f"COMMISSION: {case.commission}\nJURISDICTION: {case.jurisdiction}\n"
        f"FILED DATE: {case.filed_date or '(prospective)'}\n"
    )
    try:
        body = await llm_chat([{"role": "user", "content": prompt}], max_tokens=400, temperature=0.3)
    except Exception as e:
        log.exception("draft notice LLM failed")
        raise HTTPException(500, f"draft failed: {e}")

    r = PublicNotice(
        case_id=case_id,
        title=f"Public Notice — {case.docket_number}",
        body=body.strip(),
        channels=["newspaper", "web", "bill_insert"],
        status="draft",
    )
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="public_notice.drafted_with_ai",
        target_kind="public_notice", target_id=r.id, case_id=case_id,
    )
    return NoticeOut(id=r.id, **{k: getattr(r, k) for k in NoticeIn.model_fields})
