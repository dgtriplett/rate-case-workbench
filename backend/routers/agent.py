"""Agent orchestration endpoints.

If a deployed Mosaic agent endpoint is reachable, we proxy to it; otherwise we
run an in-process fallback so the app remains functional in demo mode.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..config import get_settings
from ..deps import CurrentUser, DBSession
from ..models import Case, DataRequest
from ..schemas import (
    CitationIn,
    DraftRequest,
    DraftResult,
    DraftStep,
    PositionCheckRequest,
    PositionCheckResult,
    PositionWarning,
)
from ..services import agent_invoke, memory as memsvc, vector_search as vs
from ..services.llm import chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/draft", response_model=DraftResult)
async def draft(body: DraftRequest, session: DBSession, _: CurrentUser) -> DraftResult:
    s = get_settings()
    dres = await session.execute(select(DataRequest).where(DataRequest.id == body.data_request_id))
    dr = dres.scalar_one_or_none()
    if not dr:
        raise HTTPException(404, "DR not found")
    cres = await session.execute(select(Case).where(Case.id == dr.case_id))
    case = cres.scalar_one()

    try:
        payload = {
            "data_request_id": str(dr.id),
            "case_id": str(case.id),
            "docket": case.docket_number,
            "jurisdiction": case.jurisdiction,
            "dr_subject": dr.subject,
            "dr_body": dr.body,
            "user_instruction": body.user_instruction,
            "extra_context": body.extra_context,
        }
        result = await agent_invoke.invoke(agent_invoke.drafter_endpoint(), payload, timeout=180.0)
        if result and "draft_text" in result:
            return DraftResult(**result)
        log.info("Drafter endpoint returned no draft_text; falling back to in-process")
    except Exception:
        log.exception("Drafter endpoint invocation failed; falling back to in-process")

    return await _in_process_draft(session, dr, case, body)


@router.post("/position-check", response_model=PositionCheckResult)
async def position_check(
    body: PositionCheckRequest, session: DBSession, _: CurrentUser
) -> PositionCheckResult:
    cres = await session.execute(select(Case).where(Case.id == body.case_id))
    case = cres.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")
    rows = await memsvc.list_for_case(
        session, case.id, jurisdiction=case.jurisdiction, include_jurisdiction=True, limit=50
    )
    if not rows:
        return PositionCheckResult(warnings=[])

    snippets = "\n".join(f"- [{r.topic_key}] {r.fact_text}" for r in rows[:25])
    prompt = (
        "You are a regulatory consistency checker for a utility rate case.\n"
        "Below is a draft response, followed by previously-established positions.\n"
        "For each prior position the draft CONTRADICTS, emit one line:\n"
        "TOPIC=<topic_key>|SEVERITY=<info|warning|conflict>|REASON=<reason>\n"
        "If no contradictions, return the single line: NONE\n\n"
        f"DRAFT:\n{body.text}\n\nPRIOR POSITIONS:\n{snippets}"
    )
    try:
        raw = await chat([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=600)
    except Exception:
        log.exception("position-check LLM call failed")
        return PositionCheckResult(warnings=[])

    warnings: list[PositionWarning] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line or line == "NONE":
            continue
        parts = {p.split("=", 1)[0]: p.split("=", 1)[1] for p in line.split("|") if "=" in p}
        topic = parts.get("TOPIC", "").strip()
        if not topic:
            continue
        sev = parts.get("SEVERITY", "warning").strip()
        reason = parts.get("REASON", "").strip()
        match = next((r for r in rows if r.topic_key == topic), None)
        if not match:
            continue
        scope = "this case" if match.case_id else f"prior case ({match.jurisdiction})"
        warnings.append(
            PositionWarning(
                topic_key=topic,
                fact_text=match.fact_text,
                severity=sev if sev in ("info", "warning", "conflict") else "warning",
                source_label=f"agent_memory[{scope}]: {reason}" if reason else f"agent_memory[{scope}]",
            )
        )
    return PositionCheckResult(warnings=warnings)


async def _in_process_draft(
    session, dr: DataRequest, case: Case, body: DraftRequest
) -> DraftResult:
    """Fallback drafter that runs in-process when the agent serving endpoint is unavailable."""
    s = get_settings()
    steps: list[DraftStep] = [DraftStep(kind="plan", label="Plan retrieval over case + jurisdiction")]

    case_hits = vs.search_case(dr.subject + "\n" + dr.body, str(case.id), top_k=6)
    steps.append(
        DraftStep(kind="retrieval", label=f"Retrieved {len(case_hits)} case chunks", detail=", ".join(h.document_title for h in case_hits[:3]))
    )
    juris_hits = vs.search_jurisdiction(dr.subject + "\n" + dr.body, case.jurisdiction, top_k=4)
    steps.append(
        DraftStep(kind="retrieval", label=f"Retrieved {len(juris_hits)} jurisdiction chunks")
    )
    prior_resp_hits = vs.search_prior_responses(dr.subject + "\n" + dr.body, case.jurisdiction, top_k=3)
    steps.append(
        DraftStep(kind="retrieval", label=f"Retrieved {len(prior_resp_hits)} prior-case responses")
    )

    memories = await memsvc.list_for_case(
        session, case.id, jurisdiction=case.jurisdiction, include_jurisdiction=True, limit=20
    )
    steps.append(DraftStep(kind="memory", label=f"Loaded {len(memories)} agent_memory rows"))

    snippets = []
    citations: list[CitationIn] = []
    for h in case_hits + juris_hits:
        snippets.append(f"[{h.document_title}] {h.chunk_text[:600]}")
        citations.append(
            CitationIn(
                source_type="kb_chunk",
                source_id=h.document_id,
                label=h.document_title,
                snippet=h.chunk_text[:300],
                page=h.page,
            )
        )
    for h in prior_resp_hits:
        snippets.append(f"[prior response — {h.document_title}] {h.chunk_text[:400]}")
        citations.append(
            CitationIn(
                source_type="prior_response",
                source_id=h.document_id,
                label=h.document_title,
                snippet=h.chunk_text[:300],
            )
        )

    memory_block = "\n".join(f"- [{m.topic_key}] {m.fact_text}" for m in memories[:10])
    evidence_block = "\n\n".join(snippets[:8]) if snippets else "(no retrieval results)"

    prompt = (
        "You are a senior regulatory affairs attorney drafting a response to a Data Request in a "
        f"utility rate case before the {case.commission} (docket {case.docket_number}, "
        f"jurisdiction {case.jurisdiction}).\n\n"
        "Draft a precise, defensible response that:\n"
        " 1. Directly addresses the DR.\n"
        " 2. Stays consistent with the positions in PRIOR POSITIONS below.\n"
        " 3. Cites specific source documents when making factual claims.\n"
        " 4. Avoids speculation and protects privileged content.\n\n"
        f"DATA REQUEST:\nSubject: {dr.subject}\n\n{dr.body}\n\n"
        f"USER INSTRUCTION: {body.user_instruction or '(none)'}\n\n"
        f"PRIOR POSITIONS (agent_memory):\n{memory_block or '(none)'}\n\n"
        f"EVIDENCE FROM CASE + JURISDICTION RETRIEVAL:\n{evidence_block}\n\n"
        "Output the response text only. Do not include greetings or signatures."
    )
    try:
        draft_text = await chat(
            [{"role": "user", "content": prompt}],
            model=s.drafter_model,
            max_tokens=2200,
            temperature=0.3,
        )
        steps.append(DraftStep(kind="llm", label=f"Drafted with {s.drafter_model}"))
    except Exception as e:
        log.exception("draft LLM call failed")
        draft_text = (
            f"[Draft generation failed: {type(e).__name__}]\n\n"
            f"The system could not generate a draft. The agent retrieved {len(case_hits)} case chunks "
            f"and {len(juris_hits)} jurisdiction chunks. Please retry or draft manually."
        )

    warnings: list[str] = []
    if memories:
        try:
            pc = await position_check(
                PositionCheckRequest(case_id=case.id, text=draft_text), session, None  # type: ignore[arg-type]
            )
            warnings = [w.fact_text for w in pc.warnings]
        except Exception:
            log.exception("inline position check failed")

    steps.append(DraftStep(kind="final", label="Final draft ready"))
    return DraftResult(
        draft_text=draft_text,
        citations=citations[:12],
        steps=steps,
        agent_trace_id=None,
        model_version=s.drafter_model,
        position_warnings=warnings,
    )
