from __future__ import annotations

import logging
import os
import uuid

from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from ...deps import DBSession, RequireAdmin
from ...models import VectorIndex
from ...config import get_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/knowledge-sources", tags=["admin-knowledge-sources"])


class VectorIndexOut(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID | None
    index_name: str
    kind: str
    endpoint_name: str


@router.get("", response_model=list[VectorIndexOut])
async def list_indices(session: DBSession, _: RequireAdmin) -> list[VectorIndexOut]:
    s = get_settings()
    res = await session.execute(select(VectorIndex).order_by(VectorIndex.kind, VectorIndex.created_at))
    rows = list(res.scalars().all())
    if not rows:
        for kind, idx in (
            ("case", s.chunks_case_index),
            ("jurisdiction", s.chunks_jurisdiction_index),
            ("prior_responses", s.prior_responses_index),
        ):
            row = VectorIndex(index_name=idx, kind=kind, endpoint_name=s.vs_endpoint)
            session.add(row)
            rows.append(row)
        await session.flush()
    return [
        VectorIndexOut(
            id=r.id, case_id=r.case_id, index_name=r.index_name, kind=r.kind, endpoint_name=r.endpoint_name
        )
        for r in rows
    ]


@router.post("/{idx_id}/reindex", response_model=VectorIndexOut)
async def reindex(idx_id: uuid.UUID, session: DBSession, _: RequireAdmin) -> VectorIndexOut:
    """Trigger a Vector Search delta-sync refresh."""
    res = await session.execute(select(VectorIndex).where(VectorIndex.id == idx_id))
    row = res.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "vector index not found")
    s = get_settings()
    try:
        client = VectorSearchClient(disable_notice=True)
        index = client.get_index(endpoint_name=row.endpoint_name, index_name=row.index_name)
        # Triggered (delta-sync) indices have sync() — managed embedding pipelines refresh on Delta change
        try:
            index.sync()
        except AttributeError:
            log.info("Index %s does not expose sync(); relying on Delta auto-sync", row.index_name)
    except Exception as e:
        log.exception("reindex failed")
        raise HTTPException(500, f"reindex failed: {e}")
    return VectorIndexOut(
        id=row.id,
        case_id=row.case_id,
        index_name=row.index_name,
        kind=row.kind,
        endpoint_name=row.endpoint_name,
    )
