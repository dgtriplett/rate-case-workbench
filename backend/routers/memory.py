from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Case
from ..schemas import MemoryOut
from ..services import memory as memsvc

router = APIRouter(prefix="/memory", tags=["memory"])


@router.get("", response_model=list[MemoryOut])
async def list_memory(
    session: DBSession,
    _: CurrentUser,
    case_id: uuid.UUID = Query(...),
    topic_key: Optional[str] = Query(default=None),
    include_jurisdiction: bool = Query(default=True),
) -> list[MemoryOut]:
    cres = await session.execute(select(Case).where(Case.id == case_id))
    case = cres.scalar_one_or_none()
    if not case:
        raise HTTPException(404, "case not found")
    rows = await memsvc.list_for_case(
        session,
        case_id,
        topic_key=topic_key,
        jurisdiction=case.jurisdiction,
        include_jurisdiction=include_jurisdiction,
    )
    return [MemoryOut.model_validate(m) for m in rows]
