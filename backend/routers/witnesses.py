from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Witness
from ..schemas import WitnessCreate, WitnessOut

router = APIRouter(prefix="/witnesses", tags=["witnesses"])


@router.get("", response_model=list[WitnessOut])
async def list_witnesses(session: DBSession, _: CurrentUser) -> list[WitnessOut]:
    res = await session.execute(select(Witness).order_by(Witness.name))
    return [WitnessOut.model_validate(w) for w in res.scalars().all()]


@router.post("", response_model=WitnessOut, status_code=201)
async def create_witness(body: WitnessCreate, session: DBSession, _: CurrentUser) -> WitnessOut:
    w = Witness(
        user_id=body.user_id,
        name=body.name,
        title=body.title,
        expertise_areas=body.expertise_areas,
        is_external=body.is_external,
    )
    session.add(w)
    await session.flush()
    return WitnessOut.model_validate(w)


@router.get("/{witness_id}", response_model=WitnessOut)
async def get_witness(witness_id: uuid.UUID, session: DBSession, _: CurrentUser) -> WitnessOut:
    res = await session.execute(select(Witness).where(Witness.id == witness_id))
    w = res.scalar_one_or_none()
    if not w:
        raise HTTPException(404, "witness not found")
    return WitnessOut.model_validate(w)
