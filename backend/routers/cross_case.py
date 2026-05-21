"""Cross-case insights — surface analogues from prior cases for the active one."""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from ..deps import CurrentUser, DBSession
from ..models import (
    AgentMemory,
    Case,
    CommissionOrder,
    IntervenorPosition,
)
from ..services.llm import chat as llm_chat

router = APIRouter(prefix="/cross-case", tags=["cross-case"])


class Analogue(BaseModel):
    prior_case_docket: str
    prior_case_name: str
    topic_key: str
    fact_text: str
    outcome: Optional[str] = None  # quoted from CommissionOrder.summary if available
    confidence: float


class InsightsOut(BaseModel):
    case_id: uuid.UUID
    analogues: list[Analogue]
    summary_text: str


@router.get("", response_model=InsightsOut)
async def get_insights(
    session: DBSession,
    _: CurrentUser,
    case_id: uuid.UUID = Query(...),
) -> InsightsOut:
    cres = await session.execute(select(Case).where(Case.id == case_id))
    case = cres.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")

    # Active intervenor positions on THIS case
    pres = await session.execute(
        select(IntervenorPosition).where(IntervenorPosition.case_id == case_id)
    )
    positions = pres.scalars().all()

    # All other cases in the same jurisdiction
    other_cases = (
        await session.execute(
            select(Case).where(
                and_(Case.id != case_id, Case.jurisdiction == case.jurisdiction)
            )
        )
    ).scalars().all()
    other_ids = [c.id for c in other_cases]
    case_by_id = {c.id: c for c in other_cases}

    # Agent memory from prior cases on the same jurisdiction
    mq = (
        select(AgentMemory)
        .where(
            or_(
                AgentMemory.case_id.in_(other_ids),
                and_(
                    AgentMemory.case_id.is_(None),
                    AgentMemory.jurisdiction == case.jurisdiction,
                ),
            )
        )
        .where(AgentMemory.is_active == True)  # noqa: E712
    )
    memories = (await session.execute(mq)).scalars().all()

    # Orders for jurisdiction (for outcome quoting)
    orders_q = await session.execute(
        select(CommissionOrder).where(CommissionOrder.case_id.in_(other_ids))
    )
    orders_by_case: dict[uuid.UUID, CommissionOrder] = {
        o.case_id: o for o in orders_q.scalars()
    }

    analogues: list[Analogue] = []
    seen_topics: set[str] = set()
    pos_topics = [p.topic.lower() for p in positions]
    for m in memories:
        tk = m.topic_key.lower()
        rel = sum(1 for pt in pos_topics if pt in tk or tk in pt)
        if rel == 0 and not any(pt in (m.fact_text or "").lower() for pt in pos_topics):
            continue
        prior_case = case_by_id.get(m.case_id) if m.case_id else None
        order = orders_by_case.get(m.case_id) if m.case_id else None
        if (m.topic_key, m.case_id) in seen_topics:
            continue
        seen_topics.add((m.topic_key, m.case_id))
        analogues.append(Analogue(
            prior_case_docket=prior_case.docket_number if prior_case else "(jurisdiction-wide)",
            prior_case_name=prior_case.name if prior_case else case.jurisdiction,
            topic_key=m.topic_key,
            fact_text=m.fact_text,
            outcome=order.summary[:300] if order and order.summary else None,
            confidence=float(m.confidence),
        ))

    summary = ""
    if analogues:
        block = "\n\n".join(
            f"- Prior {a.prior_case_docket} on {a.topic_key}: {a.fact_text[:200]}"
            + (f"\n  Outcome: {a.outcome[:200]}" if a.outcome else "")
            for a in analogues[:8]
        )
        try:
            summary = await llm_chat(
                [{
                    "role": "user",
                    "content": (
                        "In 2-3 short sentences, summarize what these prior "
                        "jurisdictional precedents suggest for the current case. "
                        "Lead with the strongest precedent. No preamble.\n\n" + block
                    ),
                }],
                max_tokens=200, temperature=0.2,
            )
        except Exception:
            pass

    return InsightsOut(case_id=case_id, analogues=analogues, summary_text=summary or "")
