"""Public comments — intake, classification, dashboard."""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import PublicComment
from ..services.audit import log_event
from ..services.llm import chat as llm_chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/public-comments", tags=["public-comments"])


class CommentIn(BaseModel):
    case_id: uuid.UUID
    source: str = "email"
    commenter_name: Optional[str] = None
    commenter_org: Optional[str] = None
    body: str
    topic_tags: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    received_date: Optional[date] = None


class CommentOut(CommentIn):
    id: uuid.UUID


class CommentsSummary(BaseModel):
    total: int
    by_sentiment: dict[str, int]
    by_source: dict[str, int]
    top_topics: list[dict]


@router.get("", response_model=list[CommentOut])
async def list_comments(
    session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)
) -> list[CommentOut]:
    res = await session.execute(
        select(PublicComment).where(PublicComment.case_id == case_id).order_by(PublicComment.created_at.desc())
    )
    return [CommentOut(id=r.id, **{k: getattr(r, k) for k in CommentIn.model_fields}) for r in res.scalars()]


@router.get("/summary", response_model=CommentsSummary)
async def summary(session: DBSession, _: CurrentUser, case_id: uuid.UUID = Query(...)) -> CommentsSummary:
    rows = (await session.execute(
        select(PublicComment).where(PublicComment.case_id == case_id)
    )).scalars().all()
    by_sent: dict[str, int] = {}
    by_src: dict[str, int] = {}
    topic_counts: dict[str, int] = {}
    for r in rows:
        by_sent[r.sentiment] = by_sent.get(r.sentiment, 0) + 1
        by_src[r.source] = by_src.get(r.source, 0) + 1
        for t in (r.topic_tags or []):
            topic_counts[t] = topic_counts.get(t, 0) + 1
    top_topics = [{"topic": t, "count": c} for t, c in sorted(topic_counts.items(), key=lambda x: -x[1])[:10]]
    return CommentsSummary(total=len(rows), by_sentiment=by_sent, by_source=by_src, top_topics=top_topics)


@router.post("", response_model=CommentOut, status_code=201)
async def create_comment(body: CommentIn, session: DBSession, user: CurrentUser) -> CommentOut:
    # Auto-classify if no tags / sentiment was provided
    if not body.topic_tags or body.sentiment == "neutral":
        try:
            cls = await _classify(body.body)
            if not body.topic_tags:
                body.topic_tags = cls.get("topics", [])
            if body.sentiment == "neutral":
                body.sentiment = cls.get("sentiment", "neutral")
        except Exception:
            log.exception("classifier failed; storing raw comment")

    r = PublicComment(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="public_comment.received", target_kind="public_comment",
        target_id=r.id, case_id=body.case_id, payload={"source": body.source, "sentiment": body.sentiment},
    )
    return CommentOut(id=r.id, **{k: getattr(r, k) for k in CommentIn.model_fields})


@router.delete("/{cid}")
async def delete_comment(cid: uuid.UUID, session: DBSession, _: CurrentUser) -> dict:
    res = await session.execute(select(PublicComment).where(PublicComment.id == cid))
    r = res.scalar_one_or_none()
    if r:
        await session.delete(r)
        await session.flush()
    return {"deleted": True}


async def _classify(body: str) -> dict:
    prompt = (
        "Classify this public comment for a utility rate case. Return ONLY a "
        'JSON object: {"sentiment":"positive|neutral|negative|mixed",'
        '"topics":["topic1","topic2"]} where topics is 1-3 short kebab-case '
        "labels (e.g. rate-increase, low-income, reliability, decarbonization, "
        "renewables, customer-service, gas-system, storm-recovery, executive-pay). "
        "No prose, no markdown fences.\n\nCOMMENT:\n" + body[:3000]
    )
    raw = await llm_chat([{"role": "user", "content": prompt}], max_tokens=200, temperature=0.0)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)
    return json.loads(raw)
