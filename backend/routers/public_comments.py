"""Public comments — intake, classification, dashboard, social ingestion."""
from __future__ import annotations

import asyncio
import json
import logging
import random
import re
import uuid
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case, PublicComment
from ..services.audit import log_event
from ..services.llm import chat as llm_chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/public-comments", tags=["public-comments"])


class CommentIn(BaseModel):
    case_id: uuid.UUID
    source: str = "email"
    platform: Optional[str] = None
    source_handle: Optional[str] = None
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
    # Auto-classify (timeout-bounded so a slow/down LLM never blocks intake).
    if not body.topic_tags or body.sentiment == "neutral":
        try:
            cls = await asyncio.wait_for(_classify(body.body), timeout=6.0)
            if not body.topic_tags:
                body.topic_tags = cls.get("topics", []) or []
            if body.sentiment == "neutral":
                body.sentiment = cls.get("sentiment", "neutral") or "neutral"
        except asyncio.TimeoutError:
            log.warning("comment classifier timed out; storing raw comment")
        except Exception:
            log.exception("classifier failed; storing raw comment")

    r = PublicComment(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="public_comment.received", target_kind="public_comment",
        target_id=r.id, case_id=body.case_id,
        payload={"source": body.source, "platform": body.platform, "sentiment": body.sentiment},
    )
    return CommentOut(id=r.id, **{k: getattr(r, k) for k in CommentIn.model_fields})


class IngestRequest(BaseModel):
    platforms: list[str] = Field(default_factory=lambda: ["twitter", "facebook", "reddit", "nextdoor", "youtube"])
    count: int = 8


class IngestResult(BaseModel):
    inserted: int
    by_platform: dict[str, int]


@router.post("/ingest-social", response_model=IngestResult)
async def ingest_social(
    body: IngestRequest,
    session: DBSession,
    user: CurrentUser,
    case_id: uuid.UUID = Query(...),
) -> IngestResult:
    """Simulate ingesting public comments from social-listening platforms.

    In production this endpoint would call the platform APIs (X/Twitter v2,
    Facebook Graph, Reddit search, Nextdoor public posts, YouTube comments)
    or a vendor like Brandwatch / Sprinklr / Talkwalker. For the demo we ask
    Claude to generate a realistic batch of comments keyed off the live case
    context (utility, docket, jurisdiction) so the data feels grounded.
    """
    case = (await session.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")

    allowed = {"twitter", "facebook", "reddit", "nextdoor", "youtube"}
    platforms = [p for p in body.platforms if p in allowed] or ["twitter"]
    target = max(2, min(20, body.count))

    prompt = (
        f"Generate {target} realistic social-media public comments about a utility "
        f"rate case for {case.utility_name} ({case.docket_number}, {case.jurisdiction}).\n"
        "Mix platforms across: " + ", ".join(platforms) + ".\n"
        "Mix sentiment: roughly 55% negative, 25% mixed, 15% positive, 5% neutral.\n"
        "Cover diverse topics: rate-increase, low-income impact, executive pay, "
        "renewables, reliability, gas decarbonization, customer service, EV charging.\n"
        "Each comment should sound like real platform language (hashtags on Twitter, "
        "longer-form on Facebook/Reddit, neighborhood-specific on Nextdoor).\n\n"
        "Return ONLY a JSON array of objects with keys: "
        '{"platform":"twitter|facebook|reddit|nextdoor|youtube",'
        '"handle":"@user or u/user",'
        '"display_name":"a name",'
        '"sentiment":"positive|neutral|negative|mixed",'
        '"topics":["topic-1","topic-2"],'
        '"body":"the comment text"}. '
        "No prose, no markdown, no code fences."
    )

    items: list[dict] = []
    try:
        raw = await asyncio.wait_for(
            llm_chat([{"role": "user", "content": prompt}], max_tokens=2400, temperature=0.85),
            timeout=45.0,
        )
        items = _safe_json_array(raw)
    except Exception:
        log.exception("LLM ingestion failed; falling back to canned dataset")

    if not items:
        items = _FALLBACK_SOCIAL[:target]

    by_platform: dict[str, int] = {}
    today = datetime.utcnow().date()
    for it in items:
        plat = (it.get("platform") or random.choice(platforms)).lower()
        if plat not in allowed:
            plat = "twitter"
        body_text = (it.get("body") or "").strip()
        if not body_text:
            continue
        sentiment = it.get("sentiment") or "neutral"
        topics = it.get("topics") or []
        r = PublicComment(
            case_id=case_id,
            source="social_media",
            platform=plat,
            source_handle=it.get("handle") or None,
            commenter_name=it.get("display_name") or None,
            body=body_text,
            topic_tags=topics if isinstance(topics, list) else [],
            sentiment=sentiment if sentiment in {"positive", "negative", "neutral", "mixed"} else "neutral",
            received_date=(today - timedelta(days=random.randint(0, 6))),
        )
        session.add(r)
        by_platform[plat] = by_platform.get(plat, 0) + 1

    await session.flush()
    await log_event(
        session, actor=user, verb="public_comments.ingested_from_social",
        target_kind="case", target_id=case_id, case_id=case_id,
        payload={"by_platform": by_platform, "total": sum(by_platform.values())},
    )
    return IngestResult(inserted=sum(by_platform.values()), by_platform=by_platform)


def _safe_json_array(raw: str) -> list[dict]:
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    start = s.find("[")
    end = s.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        arr = json.loads(s[start:end + 1])
        return arr if isinstance(arr, list) else []
    except Exception:
        return []


# Fallback dataset used if the LLM is unreachable so the demo always works.
_FALLBACK_SOCIAL: list[dict] = [
    {"platform": "twitter", "handle": "@CascadiaRatePayer", "display_name": "Jamie Park",
     "sentiment": "negative", "topics": ["rate-increase", "executive-pay"],
     "body": "Another year, another @NLPGUtility rate hike while their CEO got a $4M bonus. How is this fair? #UtilityRateCase #PayMyBill"},
    {"platform": "facebook", "display_name": "Lena Brooks",
     "sentiment": "negative", "topics": ["low-income", "rate-increase"],
     "body": "My grandma is on a fixed income and can barely afford her bill. If NLPG raises rates again she's going to have to choose between heat and medicine. The commission needs to think about real people."},
    {"platform": "reddit", "handle": "u/cascadia_engineer", "display_name": "Dev T.",
     "sentiment": "mixed", "topics": ["reliability", "capex"],
     "body": "I get that the grid needs investment after the 2024 outages, but a 12% increase feels excessive. Some of these capex projects need a hard prudence review. Discovery should dig into the engineering basis."},
    {"platform": "nextdoor", "display_name": "Maple Heights neighbor",
     "sentiment": "negative", "topics": ["storm-recovery", "reliability"],
     "body": "Tired of NLPG asking for more money when our neighborhood lost power 4 times this winter. Fix the lines THEN ask for the raise."},
    {"platform": "twitter", "handle": "@GreenCascadia", "display_name": "Green Cascadia",
     "sentiment": "negative", "topics": ["decarbonization", "gas", "capex"],
     "body": "@CPUC_X should reject NLPG's $480M gas main replacement plan. Locking in fossil infrastructure when the state has a 2045 zero-emissions target = stranded assets on ratepayers. #DecarbCascadia"},
    {"platform": "youtube", "handle": "@LocalNewsCascadia", "display_name": "Local News Cascadia",
     "sentiment": "mixed", "topics": ["rate-increase", "small-business"],
     "body": "Coverage of the NLPG rate case. Small business owners we spoke to are split — some say grid investment is overdue, others say a 12% hike will close their doors. Watch the full segment."},
    {"platform": "reddit", "handle": "u/electric_eel_42", "display_name": "ElectricEel42",
     "sentiment": "positive", "topics": ["reliability", "climate"],
     "body": "Look, I don't love a rate increase either, but the wildfire hardening they're proposing is the kind of capex we actually need. Pay now or pay way more after the next fire."},
    {"platform": "facebook", "display_name": "Cascadia Climate Action",
     "sentiment": "negative", "topics": ["decarbonization", "renewables"],
     "body": "Tell the CPUC-X to reject NLPG's plan to keep expanding gas service. We need renewable investment, not 50 more years of methane infrastructure."},
]


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
