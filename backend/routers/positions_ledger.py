"""Positions Ledger — a cross-artifact view of every position the utility
has taken on each topic, with drift detection across drafts.
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import (
    AgentMemory,
    Case,
    DataRequest,
    Response as ResponseModel,
    Testimony,
)
from ..services.llm import chat as llm_chat

router = APIRouter(prefix="/positions-ledger", tags=["positions-ledger"])


class LedgerStatement(BaseModel):
    artifact_kind: str  # filed_response | testimony | brief | agent_memory
    artifact_id: str
    artifact_title: str
    excerpt: str
    issued_or_filed_date: Optional[str] = None
    status: Optional[str] = None
    url: str


class LedgerTopic(BaseModel):
    topic_key: str
    statements: list[LedgerStatement]
    drift_warnings: list[str]  # AI-detected inconsistencies


class LedgerOut(BaseModel):
    case_id: uuid.UUID
    topics: list[LedgerTopic]


_TOPIC_KEYWORDS = {
    "roe": ["roe", "return on equity"],
    "capital_structure": ["capital structure", "equity ratio"],
    "depreciation": ["depreciation", "iowa curve"],
    "capex": ["capex", "capital plan", "imprudent"],
    "revenue_requirement": ["revenue requirement", "rate base"],
    "rate_design": ["rate design", "rate structure"],
    "storm_recovery": ["storm", "deferral"],
    "cost_of_service": ["cost of service", "class allocation"],
}


def _classify(text: str) -> Optional[str]:
    tl = (text or "").lower()
    for k, kws in _TOPIC_KEYWORDS.items():
        if any(kw in tl for kw in kws):
            return k
    return None


@router.get("", response_model=LedgerOut)
async def get_ledger(
    session: DBSession,
    _: CurrentUser,
    case_id: uuid.UUID = Query(...),
    detect_drift: bool = Query(default=True),
) -> LedgerOut:
    statements: dict[str, list[LedgerStatement]] = {k: [] for k in _TOPIC_KEYWORDS}

    # Approved/filed responses
    rq = (
        select(ResponseModel, DataRequest)
        .join(DataRequest, ResponseModel.data_request_id == DataRequest.id)
        .where(DataRequest.case_id == case_id)
        .where(ResponseModel.status.in_(["approved", "filed"]))
    )
    for r, dr in (await session.execute(rq)).all():
        text = r.final_text or r.draft_text or ""
        topic = _classify(text + " " + dr.subject)
        if not topic:
            continue
        statements[topic].append(LedgerStatement(
            artifact_kind="filed_response",
            artifact_id=str(r.id),
            artifact_title=f"{dr.dr_number} — {dr.subject[:80]}",
            excerpt=text[:400],
            issued_or_filed_date=r.filed_at.date().isoformat() if r.filed_at else None,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            url=f"/cases/{case_id}/discovery/{dr.id}",
        ))

    # Testimony + briefs
    tq = select(Testimony).where(Testimony.case_id == case_id)
    for t in (await session.execute(tq)).scalars():
        text = t.final_text or t.draft_text or ""
        topic = _classify(text + " " + (t.title or ""))
        if not topic:
            continue
        statements[topic].append(LedgerStatement(
            artifact_kind="brief" if t.kind.value in ("initial_brief", "reply_brief") else "testimony",
            artifact_id=str(t.id),
            artifact_title=f"{t.kind.value.replace('_', ' ').title()}: {t.title}",
            excerpt=text[:400],
            issued_or_filed_date=t.filed_at.date().isoformat() if t.filed_at else None,
            status=t.status.value if hasattr(t.status, "value") else str(t.status),
            url=f"/cases/{case_id}/testimony",
        ))

    # Agent memory — stored positions
    mq = select(AgentMemory).where(
        (AgentMemory.case_id == case_id)
        & (AgentMemory.is_active == True)  # noqa: E712
    )
    for m in (await session.execute(mq)).scalars():
        topic = m.topic_key if m.topic_key in statements else _classify(m.fact_text + " " + m.topic_key)
        if not topic or topic not in statements:
            # New topic from memory — include it
            statements.setdefault(topic or m.topic_key, [])
            topic = topic or m.topic_key
        statements[topic].append(LedgerStatement(
            artifact_kind="agent_memory",
            artifact_id=str(m.id),
            artifact_title=f"Stored position: {m.topic_key}",
            excerpt=m.fact_text[:400],
            issued_or_filed_date=m.created_at.date().isoformat(),
            status="active",
            url=f"/cases/{case_id}",
        ))

    topics_out: list[LedgerTopic] = []
    for k, stmts in statements.items():
        if not stmts:
            continue
        drift: list[str] = []
        if detect_drift and len(stmts) >= 2:
            combined = "\n\n".join(
                f"[{s.artifact_kind}: {s.artifact_title}] {s.excerpt}" for s in stmts
            )
            prompt = (
                f"You are checking position consistency on topic '{k}'. Below are "
                "multiple statements the utility has made on this topic across "
                "filings, testimony, and stored agent memory. Identify any "
                "INCONSISTENCIES or POSITION DRIFT in 0-3 short bullets. If "
                "everything is consistent, return EMPTY (just the word EMPTY).\n\n"
                f"{combined}"
            )
            try:
                out = await llm_chat(
                    [{"role": "user", "content": prompt}], max_tokens=400, temperature=0.0
                )
                if "EMPTY" not in out.upper()[:30]:
                    drift = [line.strip("-• ").strip() for line in out.splitlines() if line.strip()][:3]
            except Exception:
                pass
        topics_out.append(LedgerTopic(topic_key=k, statements=stmts, drift_warnings=drift))

    topics_out.sort(key=lambda t: -len(t.statements))
    return LedgerOut(case_id=case_id, topics=topics_out)
