"""Pre-filing Application Workbench — aggregates financial schedules,
cost-of-service studies, rate design proposals, and expert testimony
lineup into a single 'ready to file' package per case.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import (
    ApplicationPackage,
    CostOfServiceStudy,
    FinancialSchedule,
    RateDesignProposal,
    Testimony,
)
from ..services.audit import log_event

router = APIRouter(prefix="/application-workbench", tags=["application-workbench"])


class PackageOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    title: str
    target_filing_date: Optional[date]
    status: str
    filed_at: Optional[datetime]
    summary: Optional[str]


class PackageIn(BaseModel):
    title: str = "Application package"
    target_filing_date: Optional[date] = None
    summary: Optional[str] = None


class FinancialScheduleIn(BaseModel):
    case_id: uuid.UUID
    name: str
    kind: str
    status: str = "not_started"
    owner_user_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class FinancialScheduleOut(FinancialScheduleIn):
    id: uuid.UUID


class CostOfServiceIn(BaseModel):
    case_id: uuid.UUID
    name: str
    study_type: str = "embedded"
    source_uc_tables: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
    status: str = "in_progress"
    document_id: Optional[uuid.UUID] = None


class CostOfServiceOut(CostOfServiceIn):
    id: uuid.UUID


class RateDesignIn(BaseModel):
    case_id: uuid.UUID
    name: str
    proposed_structure: dict = Field(default_factory=dict)
    bill_impact_summary: Optional[str] = None
    status: str = "draft"


class RateDesignOut(RateDesignIn):
    id: uuid.UUID


class WorkbenchSnapshot(BaseModel):
    package: Optional[PackageOut]
    financial_schedules: list[FinancialScheduleOut]
    cost_of_service: list[CostOfServiceOut]
    rate_design: list[RateDesignOut]
    testimony_count: int
    testimony_filed_count: int
    ready_to_file: bool
    blockers: list[str]


# ---------------------------------------------------------------------------
# Aggregate snapshot
# ---------------------------------------------------------------------------


@router.get("/snapshot", response_model=WorkbenchSnapshot)
async def snapshot(
    session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)
) -> WorkbenchSnapshot:
    pres = (await session.execute(
        select(ApplicationPackage).where(ApplicationPackage.case_id == case_id)
    )).scalar_one_or_none()
    fs = (await session.execute(
        select(FinancialSchedule).where(FinancialSchedule.case_id == case_id)
    )).scalars().all()
    cs = (await session.execute(
        select(CostOfServiceStudy).where(CostOfServiceStudy.case_id == case_id)
    )).scalars().all()
    rd = (await session.execute(
        select(RateDesignProposal).where(RateDesignProposal.case_id == case_id)
    )).scalars().all()
    test = (await session.execute(
        select(Testimony).where(Testimony.case_id == case_id)
    )).scalars().all()
    t_total = len(test)
    t_filed = sum(1 for t in test if (hasattr(t.status, "value") and t.status.value == "filed") or str(t.status) == "filed")

    blockers: list[str] = []
    if not fs:
        blockers.append("No financial schedules added")
    elif any(s.status != "complete" for s in fs):
        blockers.append(f"{sum(1 for s in fs if s.status != 'complete')} financial schedule(s) incomplete")
    if not cs:
        blockers.append("No cost-of-service study")
    if not rd:
        blockers.append("No rate design proposal")
    if t_total == 0:
        blockers.append("No expert testimony drafted yet")
    ready = len(blockers) == 0

    return WorkbenchSnapshot(
        package=PackageOut(
            id=pres.id, case_id=pres.case_id, title=pres.title,
            target_filing_date=pres.target_filing_date, status=pres.status,
            filed_at=pres.filed_at, summary=pres.summary,
        ) if pres else None,
        financial_schedules=[FinancialScheduleOut(id=r.id, **{k: getattr(r, k) for k in FinancialScheduleIn.model_fields}) for r in fs],
        cost_of_service=[CostOfServiceOut(id=r.id, **{k: getattr(r, k) for k in CostOfServiceIn.model_fields}) for r in cs],
        rate_design=[RateDesignOut(id=r.id, **{k: getattr(r, k) for k in RateDesignIn.model_fields}) for r in rd],
        testimony_count=t_total, testimony_filed_count=t_filed,
        ready_to_file=ready, blockers=blockers,
    )


# ---------------------------------------------------------------------------
# Package CRUD + filing
# ---------------------------------------------------------------------------


@router.put("/{case_id}", response_model=PackageOut)
async def upsert_package(
    case_id: uuid.UUID, body: PackageIn, session: DBSession, user: CurrentUser
) -> PackageOut:
    res = await session.execute(
        select(ApplicationPackage).where(ApplicationPackage.case_id == case_id)
    )
    p = res.scalar_one_or_none()
    if p is None:
        p = ApplicationPackage(case_id=case_id, **body.model_dump(mode="json"))
        session.add(p)
        verb = "application_package.created"
    else:
        for k, v in body.model_dump(mode="json", exclude_unset=True).items():
            setattr(p, k, v)
        verb = "application_package.updated"
    await session.flush()
    await log_event(
        session, actor=user, verb=verb, target_kind="application_package",
        target_id=p.id, case_id=case_id, payload={"status": p.status},
    )
    return PackageOut(
        id=p.id, case_id=p.case_id, title=p.title,
        target_filing_date=p.target_filing_date, status=p.status,
        filed_at=p.filed_at, summary=p.summary,
    )


@router.post("/{case_id}/file", response_model=PackageOut)
async def file_application(
    case_id: uuid.UUID, session: DBSession, user: CurrentUser
) -> PackageOut:
    snap = await snapshot(session, user, case_id=case_id)
    if not snap.ready_to_file:
        raise HTTPException(409, f"Cannot file — blockers: {', '.join(snap.blockers)}")
    res = await session.execute(
        select(ApplicationPackage).where(ApplicationPackage.case_id == case_id)
    )
    p = res.scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "no application package; create one first")
    p.status = "filed"
    p.filed_at = datetime.now(timezone.utc)
    p.locked_by_user_id = user.id
    await session.flush()
    await log_event(
        session, actor=user, verb="application.filed",
        target_kind="application_package", target_id=p.id, case_id=case_id,
        payload={"filed_at": p.filed_at.isoformat()},
    )
    return PackageOut(
        id=p.id, case_id=p.case_id, title=p.title,
        target_filing_date=p.target_filing_date, status=p.status,
        filed_at=p.filed_at, summary=p.summary,
    )


# ---------------------------------------------------------------------------
# Component CRUD — financial schedules, cost-of-service, rate design
# ---------------------------------------------------------------------------


def _make_crud(prefix: str, Model, In, Out):
    """Generate compact CRUD endpoints for a child entity."""
    sub = APIRouter()

    @sub.get("", response_model=list[Out])
    async def _list(session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)):
        rows = (await session.execute(select(Model).where(Model.case_id == case_id))).scalars().all()
        return [Out(id=r.id, **{k: getattr(r, k) for k in In.model_fields}) for r in rows]

    @sub.post("", response_model=Out, status_code=201)
    async def _create(body: In, session: DBSession, user: CurrentUser):
        r = Model(**body.model_dump(mode="json"))
        session.add(r)
        await session.flush()
        await log_event(
            session, actor=user, verb=f"{prefix}.created",
            target_kind=prefix, target_id=r.id, case_id=body.case_id,
            payload={"name": body.name},
        )
        return Out(id=r.id, **{k: getattr(r, k) for k in In.model_fields})

    @sub.patch("/{row_id}", response_model=Out)
    async def _patch(row_id: uuid.UUID, body: In, session: DBSession, _: CurrentUser):
        res = await session.execute(select(Model).where(Model.id == row_id))
        r = res.scalar_one_or_none()
        if not r:
            raise HTTPException(404, "not found")
        for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
            setattr(r, k, v)
        await session.flush()
        return Out(id=r.id, **{k: getattr(r, k) for k in In.model_fields})

    @sub.delete("/{row_id}")
    async def _delete(row_id: uuid.UUID, session: DBSession, _: CurrentUser):
        res = await session.execute(select(Model).where(Model.id == row_id))
        r = res.scalar_one_or_none()
        if r:
            await session.delete(r)
            await session.flush()
        return {"deleted": True}

    return sub


router.include_router(_make_crud("financial_schedule", FinancialSchedule, FinancialScheduleIn, FinancialScheduleOut), prefix="/financial-schedules")
router.include_router(_make_crud("cost_of_service", CostOfServiceStudy, CostOfServiceIn, CostOfServiceOut), prefix="/cost-of-service")
router.include_router(_make_crud("rate_design", RateDesignProposal, RateDesignIn, RateDesignOut), prefix="/rate-design")
