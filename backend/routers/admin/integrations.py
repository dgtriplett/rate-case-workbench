"""External-system integration registrations (commission portal feeds, email
connectors, webhook destinations, ingest pipelines). Stored as JSON rows in
``settings`` under the ``integrations`` key.

This is also where the inbound DR webhook lives (`POST /webhook/data-request`)
so external systems can push DRs straight into the inbox.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ...deps import CurrentUser, DBSession, RequireAdmin
from ...models import Case, DataRequest, DRStatus, Setting
from ...services.audit import log_event

router = APIRouter(prefix="/integrations", tags=["admin-integrations"])

KEY = "integrations"


class Integration(BaseModel):
    id: str
    name: str
    kind: str  # email | portal | webhook | lakeflow | custom
    status: str = "active"  # active | paused
    detail: Optional[str] = None
    secret_ref: Optional[str] = None  # secret scope/key reference (string only)
    last_event_at: Optional[datetime] = None
    config: dict[str, Any] = {}


DEFAULTS: list[dict[str, Any]] = [
    {
        "id": "puc-portal",
        "name": "CPUC-X eFiling portal",
        "kind": "portal",
        "status": "active",
        "detail": "Polls the public commission filing portal every 15 minutes",
        "config": {"poll_interval_minutes": 15, "url": "https://example.cpuc-x.gov/efiling"},
    },
    {
        "id": "service-list",
        "name": "Service-list email connector",
        "kind": "email",
        "status": "active",
        "detail": "Parses inbound DRs from the official service-list email account",
        "config": {"mailbox": "ratecase@nlpg.example", "parser": "default-dr-parser-v2"},
    },
    {
        "id": "intervenor-webhook",
        "name": "Intervenor counsel webhook",
        "kind": "webhook",
        "status": "active",
        "detail": "Accepts POST /api/v1/webhook/data-request from external counsel systems",
        "config": {"endpoint": "/api/v1/webhook/data-request"},
    },
    {
        "id": "lakeflow-csv",
        "name": "Lakeflow ingest (structured DRs)",
        "kind": "lakeflow",
        "status": "active",
        "detail": "Streams structured DR rows (CSV/JSON) → Lakebase via Lakeflow Connect",
        "config": {"source": "s3://nlpg-regulatory/dr-feed/"},
    },
]


async def _load(session) -> list[Integration]:
    res = await session.execute(
        select(Setting).where(Setting.key == KEY, Setting.scope == "global")
    )
    s = res.scalar_one_or_none()
    if s is None:
        s = Setting(key=KEY, scope="global", value_json={"items": DEFAULTS})
        session.add(s)
        await session.flush()
    return [Integration(**t) for t in (s.value_json or {}).get("items", [])]


async def _save(session, items: list[Integration]) -> None:
    res = await session.execute(
        select(Setting).where(Setting.key == KEY, Setting.scope == "global")
    )
    s = res.scalar_one_or_none()
    body = {"items": [i.model_dump(mode="json") for i in items]}
    if s is None:
        session.add(Setting(key=KEY, scope="global", value_json=body))
    else:
        s.value_json = body
    await session.flush()


@router.get("", response_model=list[Integration])
async def list_integrations(session: DBSession, _: CurrentUser) -> list[Integration]:
    return await _load(session)


@router.post("", response_model=Integration, status_code=201)
async def create_integration(
    body: Integration, session: DBSession, _: RequireAdmin
) -> Integration:
    items = await _load(session)
    if any(i.id == body.id for i in items):
        raise HTTPException(400, "integration id already exists")
    items.append(body)
    await _save(session, items)
    return body


@router.patch("/{integration_id}", response_model=Integration)
async def patch_integration(
    integration_id: str, body: Integration, session: DBSession, _: RequireAdmin
) -> Integration:
    items = await _load(session)
    for i, cur in enumerate(items):
        if cur.id == integration_id:
            items[i] = body
            await _save(session, items)
            return body
    raise HTTPException(404, "not found")


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: str, session: DBSession, _: RequireAdmin
) -> dict:
    items = await _load(session)
    keep = [i for i in items if i.id != integration_id]
    await _save(session, keep)
    return {"deleted": True}
