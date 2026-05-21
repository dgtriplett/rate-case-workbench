"""Notifications for the current user.

Aggregates work that needs the user's attention across the workflow:
  - DRs assigned to me as witness (drafting)
  - DRs assigned to me as reviewer (in_review)
  - Responses pending approval if I have approver role
  - Approved responses ready to file
  - Upcoming DR deadlines (next 48h)
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from ..auth import get_user_roles
from ..deps import CurrentUser, DBSession
from ..models import (
    DRStatus,
    DataRequest,
    Response,
    ResponseStatus,
    Witness,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationItem(BaseModel):
    id: str
    kind: str          # assigned_dr | review_pending | approval_pending | filing_pending | due_soon
    title: str
    detail: str
    case_id: str | None = None
    target_kind: str
    target_id: str
    severity: str = "info"  # info | warning | urgent
    timestamp: datetime | None = None


@router.get("", response_model=list[NotificationItem])
async def list_notifications(
    session: DBSession, user: CurrentUser
) -> list[NotificationItem]:
    items: list[NotificationItem] = []
    role_map = await get_user_roles(session, user)
    global_roles = set(role_map.get("global", []))

    # Witness rows linked to this user
    wres = await session.execute(select(Witness).where(Witness.user_id == user.id))
    my_witness_ids = [w.id for w in wres.scalars().all()]

    # Assigned to me as witness, still needing drafting
    if my_witness_ids:
        q = (
            select(DataRequest)
            .where(DataRequest.assigned_witness_id.in_(my_witness_ids))
            .where(DataRequest.status.in_([DRStatus.assigned, DRStatus.drafting]))
            .order_by(DataRequest.due_date.asc())
            .limit(20)
        )
        for dr in (await session.execute(q)).scalars().all():
            items.append(
                NotificationItem(
                    id=f"dr-{dr.id}",
                    kind="assigned_dr",
                    title=f"Draft response for {dr.dr_number}",
                    detail=dr.subject[:140],
                    case_id=str(dr.case_id),
                    target_kind="data_request",
                    target_id=str(dr.id),
                    severity=_due_severity(dr.due_date),
                    timestamp=dr.updated_at,
                )
            )

    # Assigned to me as reviewer
    rq = (
        select(DataRequest)
        .where(DataRequest.assigned_reviewer_id == user.id)
        .where(DataRequest.status == DRStatus.in_review)
        .order_by(DataRequest.due_date.asc())
        .limit(20)
    )
    for dr in (await session.execute(rq)).scalars().all():
        items.append(
            NotificationItem(
                id=f"review-{dr.id}",
                kind="review_pending",
                title=f"Review {dr.dr_number}",
                detail=dr.subject[:140],
                case_id=str(dr.case_id),
                target_kind="data_request",
                target_id=str(dr.id),
                severity=_due_severity(dr.due_date),
                timestamp=dr.updated_at,
            )
        )

    # Approvers see all in_review responses
    if "approver" in global_roles or "admin" in global_roles:
        aq = (
            select(Response, DataRequest)
            .join(DataRequest, Response.data_request_id == DataRequest.id)
            .where(Response.status == ResponseStatus.in_review)
            .where(Response.is_current == True)  # noqa: E712
            .order_by(Response.updated_at.desc())
            .limit(20)
        )
        for resp, dr in (await session.execute(aq)).all():
            items.append(
                NotificationItem(
                    id=f"approve-{resp.id}",
                    kind="approval_pending",
                    title=f"Approve response to {dr.dr_number}",
                    detail=dr.subject[:140],
                    case_id=str(dr.case_id),
                    target_kind="response",
                    target_id=str(resp.id),
                    severity="warning",
                    timestamp=resp.updated_at,
                )
            )

    # Case managers see things ready to file
    if "case_manager" in global_roles or "admin" in global_roles or "approver" in global_roles:
        fq = (
            select(Response, DataRequest)
            .join(DataRequest, Response.data_request_id == DataRequest.id)
            .where(Response.status == ResponseStatus.approved)
            .where(Response.is_current == True)  # noqa: E712
            .order_by(Response.approved_at.desc())
            .limit(20)
        )
        for resp, dr in (await session.execute(fq)).all():
            items.append(
                NotificationItem(
                    id=f"file-{resp.id}",
                    kind="filing_pending",
                    title=f"File approved response to {dr.dr_number}",
                    detail=dr.subject[:140],
                    case_id=str(dr.case_id),
                    target_kind="response",
                    target_id=str(resp.id),
                    severity="info",
                    timestamp=resp.approved_at,
                )
            )

    # Upcoming deadlines (next 48h) across all open DRs in any case
    soon = date.today() + timedelta(days=2)
    dq = (
        select(DataRequest)
        .where(DataRequest.due_date <= soon)
        .where(DataRequest.status.notin_([DRStatus.filed, DRStatus.approved]))
        .order_by(DataRequest.due_date.asc())
        .limit(20)
    )
    for dr in (await session.execute(dq)).scalars().all():
        items.append(
            NotificationItem(
                id=f"due-{dr.id}",
                kind="due_soon",
                title=f"{dr.dr_number} due {dr.due_date.isoformat()}",
                detail=dr.subject[:140],
                case_id=str(dr.case_id),
                target_kind="data_request",
                target_id=str(dr.id),
                severity="urgent" if dr.due_date <= date.today() else "warning",
                timestamp=datetime.combine(dr.due_date, datetime.min.time()).replace(tzinfo=timezone.utc),
            )
        )

    # Stable order: severity then timestamp desc
    sev_rank = {"urgent": 0, "warning": 1, "info": 2}
    items.sort(key=lambda i: (sev_rank.get(i.severity, 9), -(i.timestamp.timestamp() if i.timestamp else 0)))
    return items[:50]


def _due_severity(due: date | None) -> str:
    if due is None:
        return "info"
    days = (due - date.today()).days
    if days <= 0:
        return "urgent"
    if days <= 3:
        return "warning"
    return "info"
