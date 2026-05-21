from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import ModelConfig
from ...schemas import ModelConfigIn, ModelConfigOut

router = APIRouter(prefix="/models", tags=["admin-models"])


@router.get("", response_model=list[ModelConfigOut])
async def list_models(session: DBSession, _: RequireAdmin) -> list[ModelConfigOut]:
    res = await session.execute(select(ModelConfig).order_by(ModelConfig.name))
    return [ModelConfigOut.model_validate(m) for m in res.scalars().all()]


@router.post("", response_model=ModelConfigOut, status_code=201)
async def create_model(
    body: ModelConfigIn, session: DBSession, _: RequireAdmin
) -> ModelConfigOut:
    m = ModelConfig(
        name=body.name, endpoint=body.endpoint, params=body.params, is_default=body.is_default
    )
    session.add(m)
    await session.flush()
    return ModelConfigOut.model_validate(m)


@router.patch("/{model_id}", response_model=ModelConfigOut)
async def update_model(
    model_id: uuid.UUID, body: ModelConfigIn, session: DBSession, _: RequireAdmin
) -> ModelConfigOut:
    res = await session.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    m = res.scalar_one_or_none()
    if not m:
        raise HTTPException(404, "model config not found")
    m.name = body.name
    m.endpoint = body.endpoint
    m.params = body.params
    m.is_default = body.is_default
    await session.flush()
    return ModelConfigOut.model_validate(m)


@router.delete("/{model_id}")
async def delete_model(model_id: uuid.UUID, session: DBSession, _: RequireAdmin) -> dict:
    res = await session.execute(select(ModelConfig).where(ModelConfig.id == model_id))
    m = res.scalar_one_or_none()
    if m:
        await session.delete(m)
        await session.flush()
    return {"deleted": True}
