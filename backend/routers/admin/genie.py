from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ...deps import CurrentUser, DBSession, RequireAdmin
from ...models import GenieRoom
from ...schemas import GenieRoomIn, GenieRoomOut
from ...services.genie_client import ask

router = APIRouter(prefix="/genie", tags=["admin-genie"])


@router.get("", response_model=list[GenieRoomOut])
@router.get("/rooms", response_model=list[GenieRoomOut])
async def list_rooms(session: DBSession, _: CurrentUser) -> list[GenieRoomOut]:
    res = await session.execute(select(GenieRoom).order_by(GenieRoom.created_at))
    return [GenieRoomOut.model_validate(r) for r in res.scalars().all()]


@router.post("", response_model=GenieRoomOut, status_code=201)
@router.post("/rooms", response_model=GenieRoomOut, status_code=201)
async def register_room(
    body: GenieRoomIn, session: DBSession, _: RequireAdmin
) -> GenieRoomOut:
    room = GenieRoom(
        case_id=body.case_id,
        room_id=body.room_id,
        label=body.label,
        description=body.description,
        allowed_roles=body.allowed_roles,
    )
    session.add(room)
    await session.flush()
    return GenieRoomOut.model_validate(room)


class AskIn(BaseModel):
    room_id: str
    question: str


@router.post("/ask")
async def ask_room(body: AskIn, session: DBSession, _: CurrentUser) -> dict:
    res = await session.execute(select(GenieRoom).where(GenieRoom.room_id == body.room_id))
    room = res.scalar_one_or_none()
    if not room:
        raise HTTPException(404, "Genie room not registered")
    result = await ask(body.question, room.room_id)
    return {
        "question": result.question,
        "sql": result.sql,
        "columns": result.columns,
        "rows": result.rows,
        "explanation": result.explanation,
        "room_id": result.space_id,
    }


@router.delete("/{room_id}")
@router.delete("/rooms/{room_id}")
async def delete_room(room_id: uuid.UUID, session: DBSession, _: RequireAdmin) -> dict:
    res = await session.execute(select(GenieRoom).where(GenieRoom.id == room_id))
    r = res.scalar_one_or_none()
    if r:
        await session.delete(r)
        await session.flush()
    return {"deleted": True}
