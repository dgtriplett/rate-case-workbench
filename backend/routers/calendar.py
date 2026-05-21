"""Unified calendar — every dated artifact on a case (or across all cases)
in one chronological feed. Also serves ICS for external calendar tools.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import (
    Case,
    ComplianceFiling,
    DataRequest,
    Hearing,
    Settlement,
    Testimony,
)

router = APIRouter(prefix="/calendar", tags=["calendar"])


class CalendarEvent(BaseModel):
    id: str
    case_id: str
    case_docket: Optional[str] = None
    title: str
    kind: str  # dr_due | testimony_due | hearing | brief_due | compliance_due | settlement_decision
    when: date
    status: str
    detail: Optional[str] = None
    url: str  # in-app deep link


@router.get("", response_model=list[CalendarEvent])
async def list_events(
    session: DBSession,
    _: CurrentUser,
    case_id: Optional[uuid.UUID] = Query(default=None),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
) -> list[CalendarEvent]:
    cases_by_id: dict[uuid.UUID, Case] = {}
    if case_id:
        c = (await session.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
        if c:
            cases_by_id[c.id] = c
    else:
        for c in (await session.execute(select(Case))).scalars():
            cases_by_id[c.id] = c

    events: list[CalendarEvent] = []

    def in_range(d: Optional[date]) -> bool:
        if d is None:
            return False
        if from_date and d < from_date:
            return False
        if to_date and d > to_date:
            return False
        return True

    # DRs
    dr_q = select(DataRequest)
    if case_id:
        dr_q = dr_q.where(DataRequest.case_id == case_id)
    for d in (await session.execute(dr_q)).scalars():
        if not in_range(d.due_date):
            continue
        c = cases_by_id.get(d.case_id)
        events.append(CalendarEvent(
            id=f"dr-{d.id}", case_id=str(d.case_id),
            case_docket=c.docket_number if c else None,
            title=f"{d.dr_number} due — {d.subject[:80]}",
            kind="dr_due", when=d.due_date, status=d.status.value if hasattr(d.status, "value") else str(d.status),
            detail=d.requester,
            url=f"/cases/{d.case_id}/discovery/{d.id}",
        ))

    # Testimony (use filed_at if filed, else updated_at as a proxy for "expected by")
    t_q = select(Testimony)
    if case_id:
        t_q = t_q.where(Testimony.case_id == case_id)
    for t in (await session.execute(t_q)).scalars():
        when = (t.filed_at.date() if t.filed_at else None) or t.updated_at.date()
        if not in_range(when):
            continue
        c = cases_by_id.get(t.case_id)
        kind = "brief_due" if t.kind.value in ("initial_brief", "reply_brief") else "testimony_due"
        events.append(CalendarEvent(
            id=f"t-{t.id}", case_id=str(t.case_id),
            case_docket=c.docket_number if c else None,
            title=f"{t.kind.value.replace('_', ' ').title()} — {t.title[:80]}",
            kind=kind, when=when,
            status=t.status.value if hasattr(t.status, "value") else str(t.status),
            url=f"/cases/{t.case_id}/testimony",
        ))

    # Hearings
    h_q = select(Hearing)
    if case_id:
        h_q = h_q.where(Hearing.case_id == case_id)
    for h in (await session.execute(h_q)).scalars():
        if not in_range(h.hearing_date):
            continue
        c = cases_by_id.get(h.case_id)
        events.append(CalendarEvent(
            id=f"h-{h.id}", case_id=str(h.case_id),
            case_docket=c.docket_number if c else None,
            title=f"Hearing: {h.title}", kind="hearing",
            when=h.hearing_date, status=h.status,
            detail=f"{h.location or ''} · ALJ {h.presiding_alj or '—'}",
            url=f"/cases/{h.case_id}/hearings",
        ))

    # Compliance filings
    cf_q = select(ComplianceFiling)
    if case_id:
        cf_q = cf_q.where(ComplianceFiling.case_id == case_id)
    for cf in (await session.execute(cf_q)).scalars():
        if not in_range(cf.due_date):
            continue
        c = cases_by_id.get(cf.case_id)
        events.append(CalendarEvent(
            id=f"cf-{cf.id}", case_id=str(cf.case_id),
            case_docket=c.docket_number if c else None,
            title=f"Compliance filing due: {cf.name}", kind="compliance_due",
            when=cf.due_date, status=cf.status,
            url=f"/cases/{cf.case_id}/compliance",
        ))

    # Settlements
    s_q = select(Settlement)
    if case_id:
        s_q = s_q.where(Settlement.case_id == case_id)
    for s in (await session.execute(s_q)).scalars():
        when = s.decision_date or s.proposed_date
        if not in_range(when):
            continue
        c = cases_by_id.get(s.case_id)
        events.append(CalendarEvent(
            id=f"s-{s.id}", case_id=str(s.case_id),
            case_docket=c.docket_number if c else None,
            title=f"Settlement {s.status}: {s.summary[:60]}", kind="settlement_decision",
            when=when, status=s.status,
            url=f"/cases/{s.case_id}",
        ))

    events.sort(key=lambda e: e.when)
    return events


@router.get("/ics", response_class=Response)
async def ics_export(
    session: DBSession,
    user: CurrentUser,
    case_id: Optional[uuid.UUID] = Query(default=None),
) -> Response:
    events = await list_events(session, user, case_id=case_id, from_date=None, to_date=None)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RCW//Calendar//EN"]
    for ev in events:
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{ev.id}@rcw")
        d = ev.when.strftime("%Y%m%d")
        lines.append(f"DTSTART;VALUE=DATE:{d}")
        lines.append(f"DTEND;VALUE=DATE:{d}")
        summary = ev.title.replace("\n", " ")
        lines.append(f"SUMMARY:{summary}")
        if ev.detail:
            lines.append(f"DESCRIPTION:{ev.detail}")
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return Response(content="\r\n".join(lines), media_type="text/calendar; charset=utf-8")
