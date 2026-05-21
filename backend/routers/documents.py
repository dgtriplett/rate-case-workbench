from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select

from ..deps import CurrentUser, DBSession
from ..models import Classification, Document, DocumentKind
from ..schemas import DocumentOut, UploadResult
from ..services.audit import log_event
from ..services.ingest import trigger_ingest_job, upload_to_volume

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentOut])
async def list_documents(
    session: DBSession,
    _: CurrentUser,
    case_id: Optional[uuid.UUID] = Query(default=None),
    kind: Optional[str] = Query(default=None),
) -> list[DocumentOut]:
    q = select(Document)
    if case_id:
        q = q.where(Document.case_id == case_id)
    if kind:
        q = q.where(Document.kind == DocumentKind(kind))
    q = q.order_by(Document.created_at.desc()).limit(500)
    res = await session.execute(q)
    return [DocumentOut.model_validate(d) for d in res.scalars().all()]


@router.post("/upload", response_model=UploadResult)
async def upload(
    session: DBSession,
    user: CurrentUser,
    file: UploadFile = File(...),
    title: str = Form(...),
    kind: str = Form("upload"),
    classification: str = Form("public"),
    case_id: Optional[uuid.UUID] = Form(default=None),
) -> UploadResult:
    if not file.filename:
        raise HTTPException(400, "missing filename")
    data = await file.read()
    if len(data) > 75 * 1024 * 1024:
        raise HTTPException(413, "file too large (max 75MB)")
    uri, sha = upload_to_volume(file.filename, data, case_id)
    doc = Document(
        case_id=case_id,
        title=title,
        kind=DocumentKind(kind),
        uri=uri,
        sha256=sha,
        classification=Classification(classification),
        ingested_at=datetime.now(timezone.utc),
        uploaded_by=user.id,
    )
    session.add(doc)
    await session.flush()
    run_id = trigger_ingest_job(doc.id, uri)
    await log_event(
        session,
        actor=user,
        verb="document.uploaded",
        target_kind="document",
        target_id=doc.id,
        case_id=case_id,
        payload={"title": title, "size": len(data), "ingest_run_id": run_id},
    )
    return UploadResult(
        document_id=doc.id, title=doc.title, uri=doc.uri, page_count=doc.page_count, ingest_job_run_id=run_id
    )


@router.get("/{document_id}", response_model=DocumentOut)
async def get_document(document_id: uuid.UUID, session: DBSession, _: CurrentUser) -> DocumentOut:
    res = await session.execute(select(Document).where(Document.id == document_id))
    d = res.scalar_one_or_none()
    if not d:
        raise HTTPException(404, "document not found")
    return DocumentOut.model_validate(d)
