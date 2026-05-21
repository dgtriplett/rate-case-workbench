"""Hearing prep — cross-examination Q&A bank.

Stores anticipated cross-exam questions per hearing/witness and proposed
answers grounded in the case record. Includes an AI generator that uses
the witness's filed testimony + the intervenor positions to predict
likely lines of questioning.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import CrossExamQA, Hearing, IntervenorPosition, Testimony, Witness
from ..services.audit import log_event
from ..services.llm import chat as llm_chat

log = logging.getLogger(__name__)
router = APIRouter(prefix="/cross-exam", tags=["hearing-prep"])


class QAItem(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    hearing_id: Optional[uuid.UUID]
    witness_id: Optional[uuid.UUID]
    topic: str
    likely_questioner: Optional[str]
    question: str
    proposed_answer: str
    difficulty: str
    source_citation: Optional[str]
    is_practiced: bool


class QAIn(BaseModel):
    case_id: uuid.UUID
    hearing_id: Optional[uuid.UUID] = None
    witness_id: Optional[uuid.UUID] = None
    topic: str
    likely_questioner: Optional[str] = None
    question: str
    proposed_answer: str
    difficulty: str = "moderate"
    source_citation: Optional[str] = None


class GenerateRequest(BaseModel):
    case_id: uuid.UUID
    hearing_id: uuid.UUID
    witness_id: uuid.UUID
    max_questions: int = Field(default=8, ge=1, le=15)


@router.get("", response_model=list[QAItem])
async def list_qa(
    session: DBSession,
    _: CurrentUser,
    case_id: uuid.UUID = Query(...),
    hearing_id: Optional[uuid.UUID] = Query(default=None),
    witness_id: Optional[uuid.UUID] = Query(default=None),
) -> list[QAItem]:
    q = select(CrossExamQA).where(CrossExamQA.case_id == case_id)
    if hearing_id:
        q = q.where(CrossExamQA.hearing_id == hearing_id)
    if witness_id:
        q = q.where(CrossExamQA.witness_id == witness_id)
    q = q.order_by(CrossExamQA.created_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return [QAItem(**{**r.__dict__, "id": r.id}) for r in rows]


@router.post("", response_model=QAItem, status_code=201)
async def create_qa(body: QAIn, session: DBSession, user: CurrentUser) -> QAItem:
    r = CrossExamQA(**body.model_dump(mode="json"))
    session.add(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="cross_exam.qa_created",
        target_kind="cross_exam_qa", target_id=r.id, case_id=r.case_id,
        payload={"topic": r.topic, "difficulty": r.difficulty},
    )
    return QAItem(**{**r.__dict__, "id": r.id})


@router.patch("/{qa_id}", response_model=QAItem)
async def update_qa(qa_id: uuid.UUID, body: QAIn, session: DBSession, _: CurrentUser) -> QAItem:
    res = await session.execute(select(CrossExamQA).where(CrossExamQA.id == qa_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "qa not found")
    for k, v in body.model_dump(exclude={"case_id"}, mode="json").items():
        setattr(r, k, v)
    await session.flush()
    return QAItem(**{**r.__dict__, "id": r.id})


@router.post("/{qa_id}/practiced", response_model=QAItem)
async def mark_practiced(qa_id: uuid.UUID, session: DBSession, _: CurrentUser) -> QAItem:
    res = await session.execute(select(CrossExamQA).where(CrossExamQA.id == qa_id))
    r = res.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "qa not found")
    r.is_practiced = True
    await session.flush()
    return QAItem(**{**r.__dict__, "id": r.id})


@router.post("/generate", response_model=list[QAItem])
async def generate(body: GenerateRequest, session: DBSession, user: CurrentUser) -> list[QAItem]:
    """Generate likely cross-exam Q&A for a witness using their testimony +
    intervenor positions on the case."""
    hres = await session.execute(select(Hearing).where(Hearing.id == body.hearing_id))
    hearing = hres.scalar_one_or_none()
    if not hearing:
        raise HTTPException(404, "hearing not found")
    wres = await session.execute(select(Witness).where(Witness.id == body.witness_id))
    witness = wres.scalar_one_or_none()
    if not witness:
        raise HTTPException(404, "witness not found")

    # Pull this witness's filed testimony on the case
    tq = (
        select(Testimony)
        .where(Testimony.case_id == body.case_id)
        .where(Testimony.witness_id == body.witness_id)
    )
    testimonies = (await session.execute(tq)).scalars().all()
    testimony_text = "\n\n".join(
        f"[{t.kind.value if hasattr(t.kind, 'value') else t.kind}] {t.title}\n{(t.final_text or t.draft_text or '')[:1500]}"
        for t in testimonies
    ) or "(no testimony on file)"

    # Pull intervenor positions
    pq = select(IntervenorPosition).where(IntervenorPosition.case_id == body.case_id)
    positions = (await session.execute(pq)).scalars().all()
    positions_text = "\n".join(
        f"- {p.intervenor} on {p.topic}: {p.position_text[:200]}"
        for p in positions
    ) or "(no positions logged)"

    prompt = (
        f"You are preparing {witness.name} ({witness.title or 'witness'}) for "
        f"cross-examination at the hearing '{hearing.title}' on "
        f"{hearing.hearing_date.isoformat() if hearing.hearing_date else 'TBD'}.\n\n"
        f"WITNESS'S FILED TESTIMONY:\n{testimony_text}\n\n"
        f"INTERVENOR POSITIONS ON THE CASE:\n{positions_text}\n\n"
        f"Generate exactly {body.max_questions} likely cross-examination "
        "questions an intervenor counsel might ask THIS witness. For each: "
        "name the LIKELY QUESTIONER (one of: CPUC-X Staff counsel, OCA counsel, "
        "CIEUC counsel, CCAC counsel, ALJ), the TOPIC, a SHARP one-sentence "
        "QUESTION, a PROPOSED ANSWER grounded in the witness's record (3-5 "
        "sentences, witness's voice), DIFFICULTY (easy | moderate | hard), and "
        "a SOURCE CITATION the witness can reference (workpaper, exhibit, or "
        "filed schedule).\n\n"
        'Return ONLY a JSON object: {"items":[{"topic":"…",'
        '"likely_questioner":"…","question":"…","proposed_answer":"…",'
        '"difficulty":"easy|moderate|hard","source_citation":"…"}]} '
        "(no prose, no markdown fences)."
    )
    try:
        raw = await llm_chat(
            [{"role": "user", "content": prompt}],
            max_tokens=3500, temperature=0.4,
        )
    except Exception as e:
        log.exception("cross-exam generate failed")
        raise HTTPException(500, f"AI generation failed: {e}")

    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        raise HTTPException(500, "AI returned malformed JSON; try again")

    saved: list[CrossExamQA] = []
    for entry in data.get("items", []):
        if not entry.get("question") or not entry.get("proposed_answer"):
            continue
        diff = entry.get("difficulty", "moderate")
        if diff not in ("easy", "moderate", "hard"):
            diff = "moderate"
        r = CrossExamQA(
            case_id=body.case_id,
            hearing_id=body.hearing_id,
            witness_id=body.witness_id,
            topic=entry.get("topic", "general")[:255],
            likely_questioner=entry.get("likely_questioner"),
            question=entry["question"],
            proposed_answer=entry["proposed_answer"],
            difficulty=diff,
            source_citation=entry.get("source_citation"),
        )
        session.add(r)
        saved.append(r)
    await session.flush()
    await log_event(
        session, actor=user, verb="cross_exam.generated",
        target_kind="cross_exam_qa", target_id=None, case_id=body.case_id,
        payload={"hearing_id": str(body.hearing_id), "witness_id": str(body.witness_id),
                 "generated": len(saved)},
    )
    return [QAItem(**{**r.__dict__, "id": r.id}) for r in saved]
