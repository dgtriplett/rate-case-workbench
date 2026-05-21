from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import Setting

router = APIRouter(prefix="/settings", tags=["admin-settings"])


class SettingOut(BaseModel):
    id: uuid.UUID
    key: str
    value_json: dict[str, Any]
    scope: str
    case_id: Optional[uuid.UUID]


class SettingIn(BaseModel):
    key: str
    value_json: dict[str, Any]
    scope: str = "global"
    case_id: Optional[uuid.UUID] = None


@router.get("", response_model=list[SettingOut])
async def list_settings(session: DBSession, _: RequireAdmin) -> list[SettingOut]:
    res = await session.execute(select(Setting))
    return [
        SettingOut(
            id=s.id, key=s.key, value_json=s.value_json or {}, scope=s.scope, case_id=s.case_id
        )
        for s in res.scalars().all()
    ]


@router.put("/{key}", response_model=SettingOut)
async def upsert_setting(
    key: str, body: SettingIn, session: DBSession, _: RequireAdmin
) -> SettingOut:
    if body.key != key:
        raise HTTPException(400, "key mismatch")
    res = await session.execute(
        select(Setting).where(
            Setting.key == key, Setting.scope == body.scope, Setting.case_id == body.case_id
        )
    )
    s = res.scalar_one_or_none()
    if s is None:
        s = Setting(key=key, value_json=body.value_json, scope=body.scope, case_id=body.case_id)
        session.add(s)
    else:
        s.value_json = body.value_json
    await session.flush()
    return SettingOut(
        id=s.id, key=s.key, value_json=s.value_json or {}, scope=s.scope, case_id=s.case_id
    )
