"""Compliance filing tracker — post-order obligations."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import CommissionOrder, ComplianceFiling
from ..services.audit import log_event

router = APIRouter(prefix="/compliance", tags=["compliance"])


class FilingIn(BaseModel):
    case_id: uuid.UUID
    order_id: Optional[uuid.UUID] = None
    name: str
    kind: str
    due_date: Optional[date] = None
    filed_date: Optional[date] = None
    status: str = "not_started"
    owner_user_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class FilingOut(FilingIn):
    id: uuid.UUID


# Templated compliance filings auto-created when an order is issued.
DEFAULT_FILINGS: list[dict] = [
    {"name": "Compliance tariff sheets", "kind": "tariff_sheet", "offset_days": 30},
    {"name": "Rate transition customer notification plan", "kind": "rate_transition", "offset_days": 45},
    {"name": "Rider mechanism filings", "kind": "rider", "offset_days": 60},
    {"name": "Accounting order — regulatory asset amortization", "kind": "accounting_order", "offset_days": 60},
    {"name": "Annual compliance report", "kind": "report", "offset_days": 365},
]


@router.get("", response_model=list[FilingOut])
async def list_filings(
    session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)
) -> list[FilingOut]:
    res = await session.execute(
        select(ComplianceFiling)
        .where(ComplianceFiling.case_id == case_id)
        .order_by(ComplianceFiling.due_date.asc().nullslast())
    )
    return [FilingOut(**{**r.__dict__, "id": r.id}) for r in res.scalars().all()]


@router.post("", response_model=FilingOut, status_code=201)
async def create_filing(body: FilingIn, session: DBSession, user: CurrentUser) -> FilingOut:
    r = ComplianceFiling(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="compliance.filing_created",
        target_kind="compliance_filing", target_id=r.id, case_id=r.case_id,
        payload={"name": body.name, "kind": body.kind},
    )
    return FilingOut(**{**r.__dict__, "id": r.id})


@router.patch("/{filing_id}", response_model=FilingOut)
async def update_filing(filing_id: uuid.UUID, body: FilingIn, session: DBSession, user: CurrentUser) -> FilingOut:
    res = await session.execute(select(ComplianceFiling).where(ComplianceFiling.id == filing_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "filing not found")
    was_filed = r.status == "filed"
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(r, k, v)
    if r.status == "filed" and not r.filed_date:
        r.filed_date = date.today()
    await session.flush()
    if r.status == "filed" and not was_filed:
        await log_event(
            session, actor=user, verb="compliance.filed",
            target_kind="compliance_filing", target_id=r.id, case_id=r.case_id,
            payload={"name": r.name},
        )
    return FilingOut(**{**r.__dict__, "id": r.id})


@router.post("/seed-from-order/{case_id}", response_model=list[FilingOut])
async def seed_from_order(case_id: uuid.UUID, session: DBSession, user: CurrentUser) -> list[FilingOut]:
    """Auto-create the standard compliance filings derived from the case's order."""
    ores = await session.execute(select(CommissionOrder).where(CommissionOrder.case_id == case_id))
    order = ores.scalar_one_or_none()
    if not order:
        raise HTTPException(400, "no commission order on this case yet")
    base = order.effective_date or order.issued_date or date.today()
    created: list[ComplianceFiling] = []
    for tpl in DEFAULT_FILINGS:
        existing = (await session.execute(
            select(ComplianceFiling).where(
                ComplianceFiling.case_id == case_id,
                ComplianceFiling.name == tpl["name"],
            )
        )).scalar_one_or_none()
        if existing:
            continue
        r = ComplianceFiling(
            case_id=case_id, order_id=order.id,
            name=tpl["name"], kind=tpl["kind"],
            due_date=base + timedelta(days=tpl["offset_days"]),
            status="not_started",
        )
        session.add(r)
        created.append(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="compliance.seeded_from_order",
        target_kind="case", target_id=case_id, case_id=case_id,
        payload={"created": len(created)},
    )
    return [FilingOut(**{**r.__dict__, "id": r.id}) for r in created]
