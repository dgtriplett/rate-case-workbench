"""Workflow automation rules — admin-configurable triggers + actions."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession, RequireAdmin
from ..models import AutomationRule, DataRequest, DRStatus, Event, IntervenorPosition
from ..services.audit import log_event

router = APIRouter(prefix="/automation", tags=["automation"])


TRIGGER_KINDS = [
    "dr_due_in_days",
    "dr_overdue",
    "position_logged_over_threshold",
    "response_filed",
    "order_issued",
    "testimony_submitted",
]

ACTION_KINDS = [
    "notify",
    "post_audit",
    "create_compliance_filing",
    "create_testimony_stub",
]


class RuleIn(BaseModel):
    name: str
    description: Optional[str] = None
    trigger_kind: str
    trigger_config: dict = Field(default_factory=dict)
    action_kind: str
    action_config: dict = Field(default_factory=dict)
    enabled: bool = True


class RuleOut(RuleIn):
    id: uuid.UUID
    last_fired_at: Optional[datetime] = None
    fire_count: int = 0


@router.get("/rules", response_model=list[RuleOut])
async def list_rules(session: DBSession, _: CurrentUser) -> list[RuleOut]:
    res = await session.execute(select(AutomationRule).order_by(AutomationRule.created_at.desc()))
    return [RuleOut(**{**r.__dict__, "id": r.id}) for r in res.scalars()]


@router.post("/rules", response_model=RuleOut, status_code=201)
async def create_rule(body: RuleIn, session: DBSession, _: RequireAdmin) -> RuleOut:
    if body.trigger_kind not in TRIGGER_KINDS:
        raise HTTPException(400, f"trigger_kind must be one of {TRIGGER_KINDS}")
    if body.action_kind not in ACTION_KINDS:
        raise HTTPException(400, f"action_kind must be one of {ACTION_KINDS}")
    r = AutomationRule(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    return RuleOut(**{**r.__dict__, "id": r.id})


@router.patch("/rules/{rule_id}", response_model=RuleOut)
async def patch_rule(rule_id: uuid.UUID, body: RuleIn, session: DBSession, _: RequireAdmin) -> RuleOut:
    res = await session.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "rule not found")
    for k, v in body.model_dump(mode="json").items():
        setattr(r, k, v)
    await session.flush()
    return RuleOut(**{**r.__dict__, "id": r.id})


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: uuid.UUID, session: DBSession, _: RequireAdmin) -> dict:
    res = await session.execute(select(AutomationRule).where(AutomationRule.id == rule_id))
    r = res.scalar_one_or_none()
    if r:
        await session.delete(r)
        await session.flush()
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Evaluate triggers on demand — call this from a Databricks Job on schedule.
# ---------------------------------------------------------------------------


class EvalOut(BaseModel):
    rules_evaluated: int
    rules_fired: int
    fires: list[dict]


@router.post("/evaluate", response_model=EvalOut)
async def evaluate_now(session: DBSession, user: CurrentUser) -> EvalOut:
    rules = (await session.execute(
        select(AutomationRule).where(AutomationRule.enabled == True)  # noqa: E712
    )).scalars().all()
    fires: list[dict] = []
    for rule in rules:
        try:
            count = await _eval_rule(session, rule, user)
        except Exception as e:
            count = 0
            fires.append({"rule": rule.name, "error": str(e)})
        if count:
            rule.last_fired_at = datetime.now(timezone.utc)
            rule.fire_count += count
            fires.append({"rule": rule.name, "fires": count})
    await session.flush()
    return EvalOut(rules_evaluated=len(rules), rules_fired=sum(1 for f in fires if "fires" in f), fires=fires)


async def _eval_rule(session, rule: AutomationRule, user) -> int:
    fires = 0
    if rule.trigger_kind == "dr_due_in_days":
        days = int((rule.trigger_config or {}).get("days", 2))
        cutoff = date.today() + timedelta(days=days)
        candidates = (await session.execute(
            select(DataRequest)
            .where(DataRequest.due_date <= cutoff)
            .where(DataRequest.due_date >= date.today())
            .where(DataRequest.status.notin_([DRStatus.filed, DRStatus.approved]))
        )).scalars().all()
        for dr in candidates:
            await _fire_action(session, rule, user,
                               target_kind="data_request", target_id=dr.id, case_id=dr.case_id,
                               payload={"dr_number": dr.dr_number, "due_date": dr.due_date.isoformat()})
            fires += 1
    elif rule.trigger_kind == "dr_overdue":
        candidates = (await session.execute(
            select(DataRequest)
            .where(DataRequest.due_date < date.today())
            .where(DataRequest.status.notin_([DRStatus.filed, DRStatus.approved]))
        )).scalars().all()
        for dr in candidates:
            await _fire_action(session, rule, user,
                               target_kind="data_request", target_id=dr.id, case_id=dr.case_id,
                               payload={"dr_number": dr.dr_number})
            fires += 1
    elif rule.trigger_kind == "position_logged_over_threshold":
        threshold = float((rule.trigger_config or {}).get("threshold_m", 25.0))
        candidates = (await session.execute(
            select(IntervenorPosition).where(IntervenorPosition.impact_amount_m != None)  # noqa: E711
        )).scalars().all()
        for p in candidates:
            if abs(p.impact_amount_m or 0) >= threshold and p.status == "open":
                await _fire_action(session, rule, user,
                                   target_kind="intervenor_position", target_id=p.id, case_id=p.case_id,
                                   payload={"topic": p.topic, "impact_m": p.impact_amount_m})
                fires += 1
    return fires


async def _fire_action(session, rule: AutomationRule, user, *, target_kind, target_id, case_id, payload) -> None:
    if rule.action_kind == "notify" or rule.action_kind == "post_audit":
        await log_event(
            session, actor=user, verb=f"automation.{rule.name}",
            target_kind=target_kind, target_id=target_id, case_id=case_id,
            payload={"rule_id": str(rule.id), "rule_name": rule.name, **payload},
        )
    # additional action kinds can be added here
