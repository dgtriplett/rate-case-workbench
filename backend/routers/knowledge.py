from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case
from ..schemas import KnowledgeSearchQuery, SearchHit
from ..services import vector_search as vs

log = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post("/search", response_model=list[SearchHit])
async def search(body: KnowledgeSearchQuery, session: DBSession, _: CurrentUser) -> list[SearchHit]:
    if not body.query.strip():
        return []
    jurisdiction = None
    if body.case_id:
        cres = await session.execute(select(Case).where(Case.id == body.case_id))
        c = cres.scalar_one_or_none()
        if c is None:
            raise HTTPException(404, "case not found")
        jurisdiction = c.jurisdiction

    hits = []
    if body.scope in ("case", "both") and body.case_id:
        hits.extend(vs.search_case(body.query, str(body.case_id), top_k=body.top_k))
    if body.scope in ("jurisdiction", "both") and jurisdiction:
        hits.extend(vs.search_jurisdiction(body.query, jurisdiction, top_k=body.top_k))
    return [
        SearchHit(
            document_id=h.document_id,
            document_title=h.document_title,
            chunk_text=h.chunk_text,
            score=h.score,
            page=h.page,
        )
        for h in hits
        if h.document_id
    ]
