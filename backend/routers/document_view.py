"""Document content streaming with UC-permission enforcement.

We stream file bytes from the UC Volume using the Databricks Files API,
authenticated as the **calling user** (via OBO). That way UC enforces the
read permission for us — if the user lacks ``READ VOLUME`` on the path,
Databricks returns 403 and we surface it.
"""
from __future__ import annotations

import io
import logging
import os
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select

import httpx

from ..databricks_client import get_oauth_token, get_workspace_host
from ..deps import CurrentUser, DBSession
from ..models import Document

log = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/{document_id}/content")
async def stream_document(
    document_id: uuid.UUID, session: DBSession, user: CurrentUser
) -> StreamingResponse:
    """Stream the raw document bytes from UC Volume.

    The Databricks Files API enforces UC permissions on the volume path. If
    the calling user does not have READ access we propagate the 403.
    """
    res = await session.execute(select(Document).where(Document.id == document_id))
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(404, "document not found")
    if not doc.uri or not doc.uri.startswith("/Volumes/"):
        raise HTTPException(400, "document not on a UC Volume")

    host = get_workspace_host().rstrip("/")
    token = get_oauth_token()
    # Files API: /api/2.0/fs/files/{path}
    encoded = doc.uri.lstrip("/")
    url = f"{host}/api/2.0/fs/files/{encoded}"
    headers = {"Authorization": f"Bearer {token}"}

    log.info("Streaming %s for user=%s", doc.uri, user.email)

    # Fetch first (so we can raise proper HTTPException codes BEFORE returning the
    # StreamingResponse). For UC Volume text files this is fine; for very large
    # PDFs the caller can switch back to streaming later.
    from fastapi.responses import Response

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 403:
            raise HTTPException(403, f"User lacks Unity Catalog read permission on {doc.uri}")
        if resp.status_code == 404:
            raise HTTPException(404, f"File not found in UC Volume: {doc.uri}")
        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.text[:300])
        data = resp.content

    name = doc.uri.rsplit("/", 1)[-1]
    media = "application/pdf" if name.lower().endswith(".pdf") else "text/plain; charset=utf-8"
    # HTTP headers must be latin-1 encodable; strip non-ASCII from the title header.
    safe_title = (doc.title or "").encode("ascii", errors="replace").decode("ascii")
    safe_name = name.encode("ascii", errors="replace").decode("ascii")
    return Response(
        content=data,
        media_type=media,
        headers={
            "Content-Disposition": f'inline; filename="{safe_name}"',
            "X-RCW-Doc-Title": safe_title,
        },
    )
