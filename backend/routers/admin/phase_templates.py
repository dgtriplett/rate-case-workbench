"""Phase template management. Templates are stored in the ``settings`` table
under the ``phase_templates`` key.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import Setting

router = APIRouter(prefix="/phase-templates", tags=["admin-phase-templates"])

SETTING_KEY = "phase_templates"

DEFAULT_TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "generic-grc",
        "name": "Generic General Rate Case",
        "jurisdiction": "*",
        "phases": [
            {"phase_type": "pre_filing", "weeks": 8},
            {"phase_type": "filing", "weeks": 2},
            {"phase_type": "discovery", "weeks": 16},
            {"phase_type": "direct_testimony", "weeks": 4},
            {"phase_type": "rebuttal", "weeks": 4},
            {"phase_type": "surrebuttal", "weeks": 2},
            {"phase_type": "hearing", "weeks": 4},
            {"phase_type": "post_hearing_briefs", "weeks": 4},
            {"phase_type": "order", "weeks": 12},
            {"phase_type": "compliance", "weeks": 8},
        ],
    },
    {
        "id": "ny-dps",
        "name": "NY DPS Major Rate Case",
        "jurisdiction": "New York",
        "phases": [
            {"phase_type": "pre_filing", "weeks": 12},
            {"phase_type": "filing", "weeks": 2},
            {"phase_type": "discovery", "weeks": 20},
            {"phase_type": "direct_testimony", "weeks": 6},
            {"phase_type": "rebuttal", "weeks": 4},
            {"phase_type": "hearing", "weeks": 6},
            {"phase_type": "post_hearing_briefs", "weeks": 6},
            {"phase_type": "order", "weeks": 16},
            {"phase_type": "compliance", "weeks": 12},
        ],
    },
    {
        "id": "cpuc-grc",
        "name": "CPUC General Rate Case",
        "jurisdiction": "California",
        "phases": [
            {"phase_type": "pre_filing", "weeks": 16},
            {"phase_type": "filing", "weeks": 2},
            {"phase_type": "discovery", "weeks": 24},
            {"phase_type": "direct_testimony", "weeks": 8},
            {"phase_type": "rebuttal", "weeks": 6},
            {"phase_type": "hearing", "weeks": 8},
            {"phase_type": "post_hearing_briefs", "weeks": 8},
            {"phase_type": "order", "weeks": 20},
            {"phase_type": "compliance", "weeks": 16},
        ],
    },
]


class PhaseTemplate(BaseModel):
    id: str
    name: str
    jurisdiction: str = "*"
    phases: list[dict[str, Any]] = Field(default_factory=list)


async def _load(session) -> list[PhaseTemplate]:
    res = await session.execute(
        select(Setting).where(Setting.key == SETTING_KEY, Setting.scope == "global")
    )
    s = res.scalar_one_or_none()
    if s is None or not s.value_json or "templates" not in s.value_json:
        # Seed defaults on first access
        s = Setting(key=SETTING_KEY, scope="global", value_json={"templates": DEFAULT_TEMPLATES})
        session.add(s)
        await session.flush()
    return [PhaseTemplate(**t) for t in s.value_json.get("templates", [])]


async def _save(session, templates: list[PhaseTemplate]) -> None:
    res = await session.execute(
        select(Setting).where(Setting.key == SETTING_KEY, Setting.scope == "global")
    )
    s = res.scalar_one_or_none()
    if s is None:
        s = Setting(
            key=SETTING_KEY,
            scope="global",
            value_json={"templates": [t.model_dump(mode="json") for t in templates]},
        )
        session.add(s)
    else:
        s.value_json = {"templates": [t.model_dump(mode="json") for t in templates]}
    await session.flush()


@router.get("", response_model=list[PhaseTemplate])
async def list_templates(session: DBSession, _: RequireAdmin) -> list[PhaseTemplate]:
    return await _load(session)


@router.post("", response_model=PhaseTemplate, status_code=201)
async def create_template(
    body: PhaseTemplate, session: DBSession, _: RequireAdmin
) -> PhaseTemplate:
    templates = await _load(session)
    if any(t.id == body.id for t in templates):
        raise HTTPException(400, "template id already exists")
    templates.append(body)
    await _save(session, templates)
    return body


@router.delete("/{template_id}")
async def delete_template(
    template_id: str, session: DBSession, _: RequireAdmin
) -> dict:
    templates = await _load(session)
    remaining = [t for t in templates if t.id != template_id]
    await _save(session, remaining)
    return {"deleted": True}
