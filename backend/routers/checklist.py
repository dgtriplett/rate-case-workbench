"""Best-practices checklists for response + testimony drafts.

Checklists are stored as JSON in the ``settings`` table (so admins can edit
them globally or per-case via the existing settings UI). Each draft is run
through an LLM scoring pass that returns a verdict (pass | needs_attention |
fail) and short rationale for each item.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case, Response, Setting, Testimony
from ..services.llm import chat as llm_chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/checklist", tags=["checklist"])


RESPONSE_KEY = "checklist.response"
TESTIMONY_KEY = "checklist.testimony"


DEFAULT_RESPONSE_ITEMS = [
    {"id": "directly_answers", "title": "Directly answers each part of the data request"},
    {"id": "cites_sources", "title": "Cites specific workpapers, schedules, or exhibits for factual claims"},
    {"id": "consistent_positions", "title": "Consistent with positions taken on prior DRs / testimony in this case"},
    {"id": "no_speculation", "title": "Avoids speculation, hedging, or unsupported assertions"},
    {"id": "privilege_check", "title": "Privileged or work-product content is properly flagged"},
    {"id": "objection_handled", "title": "Any objections (scope, burden, confidentiality) are clearly stated up front"},
    {"id": "units_specified", "title": "Numeric values include units ($M, %, MWh, customers, etc.)"},
    {"id": "tone_professional", "title": "Tone is professional, neutral, and appropriate for the commission"},
]

DEFAULT_TESTIMONY_ITEMS = [
    {"id": "qualifications_intro", "title": "Begins with witness qualifications and scope of testimony"},
    {"id": "headings_clear", "title": "Section headings cleanly mirror the order of the issues addressed"},
    {"id": "exhibits_referenced", "title": "Every numeric claim references a supporting exhibit / workpaper"},
    {"id": "policy_position_clear", "title": "Policy positions are explicitly stated with rationale"},
    {"id": "prior_orders_addressed", "title": "Addresses or distinguishes relevant prior commission orders"},
    {"id": "rebuttal_anticipated", "title": "Anticipates and pre-empts likely rebuttal arguments"},
    {"id": "summary_paragraph", "title": "Closes with a concise summary or recommendation"},
    {"id": "no_jargon_unexplained", "title": "Defines technical jargon on first use"},
]


class ChecklistItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None


class ChecklistOut(BaseModel):
    kind: str  # "response" | "testimony"
    items: list[ChecklistItem]


class ChecklistEvaluation(BaseModel):
    id: str
    title: str
    verdict: str  # pass | needs_attention | fail | unable_to_assess
    rationale: str
    suggested_edit: Optional[str] = None  # concrete inline fix for failures
    suggested_addendum: Optional[str] = None  # text to append if the gap is missing content


class EvalRequest(BaseModel):
    kind: str  # "response" | "testimony"
    target_id: Optional[uuid.UUID] = None
    text: Optional[str] = None
    case_id: Optional[uuid.UUID] = None


class EvalResult(BaseModel):
    kind: str
    items: list[ChecklistEvaluation]


async def _load_items(session, kind: str) -> list[ChecklistItem]:
    key = RESPONSE_KEY if kind == "response" else TESTIMONY_KEY
    defaults = DEFAULT_RESPONSE_ITEMS if kind == "response" else DEFAULT_TESTIMONY_ITEMS
    res = await session.execute(
        select(Setting).where(Setting.key == key, Setting.scope == "global")
    )
    s = res.scalar_one_or_none()
    if s is None:
        s = Setting(key=key, scope="global", value_json={"items": defaults})
        session.add(s)
        await session.flush()
        items = defaults
    else:
        items = (s.value_json or {}).get("items", defaults)
    return [ChecklistItem(**it) for it in items]


@router.get("/{kind}", response_model=ChecklistOut)
async def list_items(kind: str, session: DBSession, _: CurrentUser) -> ChecklistOut:
    if kind not in ("response", "testimony"):
        raise HTTPException(400, "kind must be 'response' or 'testimony'")
    return ChecklistOut(kind=kind, items=await _load_items(session, kind))


@router.put("/{kind}", response_model=ChecklistOut)
async def replace_items(
    kind: str, body: ChecklistOut, session: DBSession, _: CurrentUser
) -> ChecklistOut:
    if kind not in ("response", "testimony"):
        raise HTTPException(400, "kind must be 'response' or 'testimony'")
    key = RESPONSE_KEY if kind == "response" else TESTIMONY_KEY
    res = await session.execute(
        select(Setting).where(Setting.key == key, Setting.scope == "global")
    )
    s = res.scalar_one_or_none()
    payload = {"items": [it.model_dump(mode="json") for it in body.items]}
    if s is None:
        session.add(Setting(key=key, scope="global", value_json=payload))
    else:
        s.value_json = payload
    await session.flush()
    return ChecklistOut(kind=kind, items=body.items)


async def _resolve_text(session, body: EvalRequest) -> tuple[str, Optional[uuid.UUID]]:
    if body.text and body.text.strip():
        return body.text, body.case_id
    if body.target_id is None:
        raise HTTPException(400, "Provide text or target_id")
    if body.kind == "response":
        res = await session.execute(select(Response).where(Response.id == body.target_id))
        r = res.scalar_one_or_none()
        if not r:
            raise HTTPException(404, "response not found")
        case_id = None
        if r.data_request_id:
            from ..models import DataRequest
            dres = await session.execute(select(DataRequest).where(DataRequest.id == r.data_request_id))
            dr = dres.scalar_one_or_none()
            case_id = dr.case_id if dr else None
        return r.final_text or r.draft_text or "", case_id
    if body.kind == "testimony":
        res = await session.execute(select(Testimony).where(Testimony.id == body.target_id))
        t = res.scalar_one_or_none()
        if not t:
            raise HTTPException(404, "testimony not found")
        return t.final_text or t.draft_text or "", t.case_id
    raise HTTPException(400, "unknown kind")


@router.post("/evaluate", response_model=EvalResult)
async def evaluate(body: EvalRequest, session: DBSession, _: CurrentUser) -> EvalResult:
    if body.kind not in ("response", "testimony"):
        raise HTTPException(400, "kind must be 'response' or 'testimony'")
    items = await _load_items(session, body.kind)
    text, _case_id = await _resolve_text(session, body)
    if not text.strip():
        return EvalResult(
            kind=body.kind,
            items=[
                ChecklistEvaluation(id=i.id, title=i.title, verdict="unable_to_assess", rationale="Draft is empty.")
                for i in items
            ],
        )

    item_block = "\n".join(f"- [{i.id}] {i.title}" for i in items)
    prompt = (
        "You are a senior regulatory reviewer scoring a "
        f"{body.kind} draft against a best-practices checklist.\n\n"
        "For each item, return:\n"
        " - verdict: pass | needs_attention | fail | unable_to_assess\n"
        " - rationale: one short sentence (grounded only in the draft)\n"
        " - suggested_addendum: ONLY when verdict is needs_attention or fail — "
        "a concrete 1-3 sentence paragraph the author could APPEND to the draft "
        "to close the gap. Use the same voice and naming as the draft. Omit "
        "this field entirely when verdict is pass or unable_to_assess.\n\n"
        "Return ONLY a JSON object with this shape (no prose, no markdown fences):\n"
        '{"items":[{"id":"<id>","verdict":"…","rationale":"…","suggested_addendum":"…?"}]}\n\n'
        f"CHECKLIST:\n{item_block}\n\nDRAFT:\n{text[:8000]}"
    )
    try:
        raw = await llm_chat(
            [{"role": "user", "content": prompt}], max_tokens=1800, temperature=0.0
        )
    except Exception:
        log.exception("checklist LLM call failed")
        return EvalResult(
            kind=body.kind,
            items=[
                ChecklistEvaluation(id=i.id, title=i.title, verdict="unable_to_assess", rationale="Model unavailable.")
                for i in items
            ],
        )

    parsed: list[ChecklistEvaluation] = []
    try:
        # Extract JSON
        s = raw.strip()
        if s.startswith("```"):
            import re
            s = re.sub(r"^```(?:json)?\s*", "", s)
            s = re.sub(r"\s*```\s*$", "", s)
        data = json.loads(s)
        by_id = {it.id: it for it in items}
        for entry in data.get("items", []):
            iid = entry.get("id")
            if iid in by_id:
                parsed.append(
                    ChecklistEvaluation(
                        id=iid,
                        title=by_id[iid].title,
                        verdict=entry.get("verdict", "unable_to_assess"),
                        rationale=entry.get("rationale", ""),
                        suggested_edit=entry.get("suggested_edit") or None,
                        suggested_addendum=entry.get("suggested_addendum") or None,
                    )
                )
    except Exception:
        log.exception("checklist parse failed; raw=%s", raw[:200])

    seen = {e.id for e in parsed}
    for it in items:
        if it.id not in seen:
            parsed.append(
                ChecklistEvaluation(id=it.id, title=it.title, verdict="unable_to_assess", rationale="No verdict returned.")
            )
    return EvalResult(kind=body.kind, items=parsed)
