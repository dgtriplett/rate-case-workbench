from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import FeatureFlag
from ...schemas import FeatureFlagOut, FeatureFlagUpdate

router = APIRouter(prefix="/feature-flags", tags=["admin-feature-flags"])


class FeatureFlagIn(BaseModel):
    key: str
    enabled: bool = True
    description: str | None = None


DEFAULT_FLAGS = [
    ("testimony_studio", True, "Enable Testimony Studio view"),
    ("cross_case_memory", True, "Use cross-case agent memory in drafter"),
    ("genie_tool", True, "Allow drafter to call Genie for tabular evidence"),
    ("auto_redact", False, "Run redactor on every approved response"),
    ("position_check_on_submit", True, "Run position checker when submitting for review"),
]


@router.get("", response_model=list[FeatureFlagOut])
async def list_flags(session: DBSession, _: RequireAdmin) -> list[FeatureFlagOut]:
    res = await session.execute(select(FeatureFlag).order_by(FeatureFlag.key))
    rows = list(res.scalars().all())
    existing = {f.key for f in rows}
    for key, en, desc in DEFAULT_FLAGS:
        if key not in existing:
            f = FeatureFlag(key=key, enabled=en, description=desc)
            session.add(f)
            rows.append(f)
    await session.flush()
    return [FeatureFlagOut.model_validate(f) for f in rows]


@router.patch("/{key}", response_model=FeatureFlagOut)
async def update_flag(
    key: str, body: FeatureFlagUpdate, session: DBSession, _: RequireAdmin
) -> FeatureFlagOut:
    res = await session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    f = res.scalar_one_or_none()
    if f is None:
        raise HTTPException(404, "flag not found")
    f.enabled = body.enabled
    await session.flush()
    return FeatureFlagOut.model_validate(f)
