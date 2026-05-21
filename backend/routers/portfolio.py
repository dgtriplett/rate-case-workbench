"""Executive portfolio dashboard — every active case at a glance."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import (
    Case,
    CaseStatus,
    CommissionOrder,
    DRStatus,
    DataRequest,
    IntervenorPosition,
    Testimony,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


class CasePortfolioRow(BaseModel):
    case_id: uuid.UUID
    docket_number: str
    name: str
    jurisdiction: str
    status: str
    revenue_at_stake_m: Optional[float] = None
    revenue_authorized_m: Optional[float] = None
    days_to_decision: Optional[int] = None
    open_dr_count: int
    overdue_dr_count: int
    intervenor_position_impact_m: float = 0.0
    rebuttal_coverage_pct: float = 0.0
    testimony_drafts_open: int = 0
    next_milestone: Optional[str] = None
    next_milestone_date: Optional[date] = None


class PortfolioOut(BaseModel):
    rows: list[CasePortfolioRow]
    totals: dict


@router.get("", response_model=PortfolioOut)
async def get_portfolio(session: DBSession, _: CurrentUser) -> PortfolioOut:
    cases = (await session.execute(select(Case).order_by(Case.filed_date.desc().nullslast()))).scalars().all()
    if not cases:
        return PortfolioOut(rows=[], totals={})

    drs = (await session.execute(select(DataRequest))).scalars().all()
    positions = (await session.execute(select(IntervenorPosition))).scalars().all()
    testimony = (await session.execute(select(Testimony))).scalars().all()
    orders = {
        o.case_id: o
        for o in (await session.execute(select(CommissionOrder))).scalars()
    }

    rows: list[CasePortfolioRow] = []
    for c in cases:
        case_drs = [d for d in drs if d.case_id == c.id]
        open_drs = [d for d in case_drs if d.status not in (DRStatus.filed, DRStatus.approved)]
        overdue = [
            d for d in open_drs
            if d.due_date and d.due_date < date.today()
        ]
        case_positions = [p for p in positions if p.case_id == c.id]
        rebutted = [p for p in case_positions if p.status == "rebutted"]
        rebuttal_pct = (len(rebutted) / len(case_positions) * 100) if case_positions else 0.0
        impact = sum(abs(p.impact_amount_m or 0) for p in case_positions)
        case_testimony = [t for t in testimony if t.case_id == c.id]
        open_t = [t for t in case_testimony if (hasattr(t.status, "value") and t.status.value in ("draft", "in_review")) or str(t.status) in ("draft", "in_review")]

        days_to_decision = (
            (c.target_decision_date - date.today()).days
            if c.target_decision_date and c.status != CaseStatus.closed
            else None
        )

        # Crude revenue-at-stake / authorized read
        rev_stake = None
        rev_auth = None
        order = orders.get(c.id)
        if order:
            rev_auth = order.authorized_revenue_increase_m

        # Next milestone — earliest upcoming DR due date or hearing
        next_dr = sorted(
            [d for d in open_drs if d.due_date and d.due_date >= date.today()],
            key=lambda d: d.due_date,
        )
        nm_text = None
        nm_date = None
        if next_dr:
            nm_text = f"{next_dr[0].dr_number} due"
            nm_date = next_dr[0].due_date

        rows.append(CasePortfolioRow(
            case_id=c.id, docket_number=c.docket_number, name=c.name,
            jurisdiction=c.jurisdiction,
            status=c.status.value if hasattr(c.status, "value") else str(c.status),
            revenue_at_stake_m=rev_stake,
            revenue_authorized_m=rev_auth,
            days_to_decision=days_to_decision,
            open_dr_count=len(open_drs),
            overdue_dr_count=len(overdue),
            intervenor_position_impact_m=round(impact, 1),
            rebuttal_coverage_pct=round(rebuttal_pct, 1),
            testimony_drafts_open=len(open_t),
            next_milestone=nm_text,
            next_milestone_date=nm_date,
        ))

    active = [r for r in rows if r.status in ("active", "pre_filing")]
    totals = {
        "active_cases": len(active),
        "closed_cases": sum(1 for r in rows if r.status == "closed"),
        "total_open_drs": sum(r.open_dr_count for r in active),
        "total_overdue_drs": sum(r.overdue_dr_count for r in active),
        "total_position_impact_m": round(sum(r.intervenor_position_impact_m for r in active), 1),
        "total_revenue_authorized_m": round(
            sum(r.revenue_authorized_m or 0 for r in rows if r.status == "closed"), 1
        ),
    }
    return PortfolioOut(rows=rows, totals=totals)
