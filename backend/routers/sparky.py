"""Sparky — the helpful in-app chatbot.

Two modes (auto-detected from the question, but caller can hint):

1. **docs** — retrieves from the case + jurisdiction Vector Search indices and answers
   from the retrieved evidence with citations.
2. **app** — answers questions about how to use the Rate Case Workbench itself
   (workflow, screens, admin features) from a built-in knowledge file.

The endpoint streams an SSE response when ``stream=true``.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case
from ..services import vector_search as vs
from ..services.llm import chat as llm_chat
from ..config import get_settings

log = logging.getLogger(__name__)
router = APIRouter(prefix="/sparky", tags=["sparky"])


# ---------------------------------------------------------------------------
# Built-in app knowledge — answers "how do I…" questions about the workbench
# ---------------------------------------------------------------------------

APP_KNOWLEDGE = """
# Rate Case Workbench — how it works

## Top-level concept
- Everything is rooted under a **Case** (e.g. a General Rate Case at a state PUC).
- A case has **phases**: pre-filing, filing, discovery, direct testimony, rebuttal,
  surrebuttal, hearing, post-hearing briefs, order, compliance.
- Cases live together so positions stay consistent across the whole proceeding.

## Personas (left nav adapts to role)
- **Case manager**: owns the case end-to-end. Uses Case Home, Phase Board, Discovery
  Inbox, Witness Coordination, Filing Console.
- **Witness / SME**: receives assigned data requests. Uses the **Response Drafter**
  (3-pane screen) to draft answers with agent help.
- **Reviewer / Approver**: reviews drafts in the Review Queue, checks position
  consistency, approves for filing.
- **Admin**: configures cases, users, models, knowledge sources, Genie rooms, feature
  flags.

## The Response Drafter (the hero screen)
- Three panes: DR text on the left, agent chat + draft editor in the middle, evidence
  rail on the right.
- Right rail tabs: **Position consistency** (warnings when the draft contradicts a
  stored position), **Prior responses (this case)**, **Prior responses (jurisdiction)**,
  **Pinned Genie results**, **Citations**.
- The drafter uses **agent memory** in Lakebase — positions taken on prior approved
  responses are surfaced so you stay consistent across hundreds of responses.

## Data flow
- **Lakebase Postgres** = all live workflow state (cases, DRs, responses, testimony,
  agent_memory, users, settings).
- **Delta tables in Unity Catalog** = the document corpus that Vector Search indexes,
  plus tabular evidence (rate base, O&M, capex, etc.) that the Genie space queries.
- **Vector Search** = retrieval over case + jurisdiction documents.
- **Genie** = natural-language SQL over tabular evidence; results can be pinned to
  responses.
- **MLflow** = every drafter run is traced; the trace id is stored on the response so
  reviewers can replay every retrieval step.

## Common workflows
- **Answer a data request**: open Discovery Inbox → click a DR → in the Drafter, click
  "Ask agent to draft" → review evidence in the right rail → edit → submit for review.
- **Approve a response**: open Review Queue → click a draft → check position
  consistency → click Approve. The memory_writer job extracts positions into
  agent_memory for future consistency checks.
- **File a response**: from the Filing Console, click File on an approved response.
- **Upload knowledge**: Knowledge Library → Upload. File goes to UC Volume; an ingest
  job chunks + embeds it; it's then retrievable by the agent.

## Admin
- Cases: create / archive / configure phase template.
- Users & Roles: invite, grant global or per-case roles.
- Models: choose foundation model endpoint per task (drafter, summarizer, redactor).
- Knowledge sources: re-index, manage Vector Search indices.
- Genie rooms: register a Genie space per case.
- Feature flags: toggle modules.
- Audit: per-user activity + MLflow trace links.
"""


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class SparkyTurn(BaseModel):
    role: str  # user | assistant
    content: str


class SparkyAsk(BaseModel):
    question: str
    case_id: Optional[uuid.UUID] = None
    history: list[SparkyTurn] = Field(default_factory=list)
    mode_hint: Optional[str] = None  # "docs" | "app" | None (auto)
    top_k: int = 6
    stream: bool = False


class SparkyCitation(BaseModel):
    document_id: str
    document_title: str
    snippet: str
    page: Optional[int] = None
    source: str = "docs"


class SparkyAnswer(BaseModel):
    answer: str
    mode: str
    citations: list[SparkyCitation] = Field(default_factory=list)


# ---------------------------------------------------------------------------


def _classify_mode(question: str) -> str:
    q = question.lower()
    app_keywords = [
        "how do i", "how to", "where do i", "where is", "what is the", "explain",
        "what does", "this app", "the app", "this tool", "the workbench",
        "the drafter", "the inbox", "admin portal", "phase board", "shortcut",
        "navigate", "logout", "log out", "settings",
    ]
    if any(k in q for k in app_keywords):
        return "app"
    return "docs"


async def _answer_docs(
    session, case: Optional[Case], body: SparkyAsk
) -> SparkyAnswer:
    s = get_settings()
    hits: list[vs.Hit] = []
    if case:
        hits.extend(vs.search_case(body.question, str(case.id), top_k=body.top_k))
        if case.jurisdiction:
            hits.extend(vs.search_jurisdiction(body.question, case.jurisdiction, top_k=body.top_k))
    else:
        # No active case: fall back to jurisdiction-wide search of any docs in the
        # cross-case index. Best-effort.
        hits.extend(vs.search_jurisdiction(body.question, "", top_k=body.top_k))

    evidence = "\n\n".join(
        f"[{i + 1}] ({h.document_title}, p.{h.page or '?'}) {h.chunk_text[:600]}"
        for i, h in enumerate(hits[:body.top_k])
    ) or "(no documents matched)"

    history_msgs = [{"role": t.role, "content": t.content} for t in body.history[-6:]]
    sys_prompt = (
        "You are Sparky, the helpful assistant inside the Rate Case Workbench app. "
        "When the user asks about a case or about regulatory content, answer ONLY from "
        "the EVIDENCE below, and cite specific sources inline using [1], [2], … "
        "If the evidence doesn't cover the question, say so plainly. Be concise."
    )
    user_prompt = (
        f"USER QUESTION:\n{body.question}\n\n"
        f"EVIDENCE:\n{evidence}"
    )
    messages = [{"role": "system", "content": sys_prompt}, *history_msgs, {"role": "user", "content": user_prompt}]
    try:
        answer = await llm_chat(messages, max_tokens=900, temperature=0.2)
    except Exception:
        log.exception("sparky docs LLM call failed")
        answer = "I couldn't reach the model right now. Try again in a moment."

    citations = [
        SparkyCitation(
            document_id=h.document_id or "",
            document_title=h.document_title or "(untitled)",
            snippet=h.chunk_text[:300],
            page=h.page,
            source="case" if (h.case_id and case and str(case.id) == h.case_id) else "jurisdiction",
        )
        for h in hits[:body.top_k]
        if h.document_id
    ]
    return SparkyAnswer(answer=answer, mode="docs", citations=citations)


async def _answer_app(body: SparkyAsk) -> SparkyAnswer:
    history_msgs = [{"role": t.role, "content": t.content} for t in body.history[-6:]]
    sys_prompt = (
        "You are Sparky, the friendly assistant inside the Rate Case Workbench app. "
        "Answer questions about how to use the app using ONLY the APP REFERENCE below. "
        "Be concise, friendly, and walk the user through screens step by step. "
        "Use **bold** for screen names and short bullet lists where helpful."
    )
    user_prompt = (
        f"USER QUESTION:\n{body.question}\n\n"
        f"APP REFERENCE:\n{APP_KNOWLEDGE}"
    )
    messages = [{"role": "system", "content": sys_prompt}, *history_msgs, {"role": "user", "content": user_prompt}]
    try:
        answer = await llm_chat(messages, max_tokens=700, temperature=0.3)
    except Exception:
        log.exception("sparky app LLM call failed")
        answer = "I'm having trouble reaching the model right now — please try again."
    return SparkyAnswer(answer=answer, mode="app", citations=[])


@router.post("/ask", response_model=SparkyAnswer)
async def ask(body: SparkyAsk, session: DBSession, _: CurrentUser) -> SparkyAnswer:
    if not body.question.strip():
        raise HTTPException(400, "question required")
    case: Optional[Case] = None
    if body.case_id:
        res = await session.execute(select(Case).where(Case.id == body.case_id))
        case = res.scalar_one_or_none()

    mode = body.mode_hint or _classify_mode(body.question)
    if mode == "app":
        return await _answer_app(body)
    return await _answer_docs(session, case, body)


@router.post("/stream")
async def stream(body: SparkyAsk, session: DBSession, _: CurrentUser):
    """Server-Sent Events stream for Sparky.

    Emits two event types: `meta` (with mode + citations) then a sequence of
    `delta` events (token chunks), then a final `done`.
    """
    # For simplicity, we do a non-streaming call and chunk the answer to the
    # client. The frontend renders it as if it were streaming.
    answer = await ask(body, session, _)

    async def gen() -> AsyncIterator[bytes]:
        meta = {
            "mode": answer.mode,
            "citations": [c.model_dump(mode="json") for c in answer.citations],
        }
        yield f"event: meta\ndata: {json.dumps(meta)}\n\n".encode()
        chunk_size = 80
        text = answer.answer
        for i in range(0, len(text), chunk_size):
            yield f"event: delta\ndata: {json.dumps({'t': text[i:i + chunk_size]})}\n\n".encode()
            await asyncio.sleep(0.02)
        yield b"event: done\ndata: {}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
