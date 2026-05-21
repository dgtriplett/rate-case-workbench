"""Inbound DR webhook.

External systems (intervenor counsel platforms, commission portal pollers,
service-list email parsers) POST data requests here. The endpoint accepts a
minimal payload, resolves the case by docket number, and inserts a fresh DR
into the discovery inbox.

For demo purposes this endpoint is auth'd via the standard app session — in
production you'd add a shared secret header per-integration.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case, DRStatus, DataRequest
from ..services.audit import log_event

log = logging.getLogger(__name__)
router = APIRouter(prefix="/webhook", tags=["webhook"])


class IncomingDR(BaseModel):
    docket_number: str
    dr_number: str
    requester: str
    requester_kind: Optional[str] = "other"
    subject: str
    body: str
    priority: str = "normal"
    issued_date: Optional[date] = None
    due_date: Optional[date] = None
    source: Optional[str] = "webhook"


@router.post("/data-request")
async def ingest_dr(
    body: IncomingDR, session: DBSession, user: CurrentUser
) -> dict:
    cres = await session.execute(
        select(Case).where(Case.docket_number == body.docket_number)
    )
    case = cres.scalar_one_or_none()
    if not case:
        raise HTTPException(404, f"no case with docket {body.docket_number}")

    issued = body.issued_date or date.today()
    due = body.due_date or (issued + timedelta(days=14))

    dr = DataRequest(
        case_id=case.id,
        dr_number=body.dr_number,
        requester=body.requester,
        requester_kind=body.requester_kind,
        issued_date=issued,
        due_date=due,
        subject=body.subject[:512],
        body=body.body,
        priority=body.priority,
        status=DRStatus.new,
    )
    session.add(dr)
    await session.flush()
    await log_event(
        session,
        actor=user,
        verb="data_request.webhook_ingest",
        target_kind="data_request",
        target_id=dr.id,
        case_id=case.id,
        payload={"source": body.source, "dr_number": body.dr_number},
    )
    return {"ok": True, "id": str(dr.id), "dr_number": dr.dr_number}
