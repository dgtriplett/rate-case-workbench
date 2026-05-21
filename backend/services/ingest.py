"""Ingest pipeline — uploaded doc → UC Volume → chunk + summarize → Delta + VS index.

For the in-app upload, we call the Databricks Workspace API to write the file to
the configured Volume and trigger a Databricks Job that does the heavy lifting
(chunk, embed, upsert to Delta). The Delta tables are the source-of-truth that
Vector Search reads from via Delta Sync.
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Optional

from databricks.sdk import WorkspaceClient

from ..config import get_settings

log = logging.getLogger(__name__)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def upload_to_volume(filename: str, data: bytes, case_id: Optional[uuid.UUID]) -> tuple[str, str]:
    """Returns (volume_uri, sha256)."""
    s = get_settings()
    folder = str(case_id) if case_id else "_jurisdiction"
    safe_name = filename.replace("/", "_").replace("..", "_")
    target = f"{s.docs_volume}/{folder}/{uuid.uuid4().hex[:8]}_{safe_name}"
    w = WorkspaceClient()
    w.files.upload(target, data, overwrite=False)
    return target, _sha256(data)


def trigger_ingest_job(document_id: uuid.UUID, uri: str) -> Optional[str]:
    """Trigger the rcw-ingest Databricks Job. Returns the run id."""
    job_name = os.environ.get("RCW_INGEST_JOB_NAME", "rcw-ingest")
    try:
        w = WorkspaceClient()
        jobs = list(w.jobs.list(name=job_name))
        if not jobs:
            log.warning("Ingest job %s not found", job_name)
            return None
        run = w.jobs.run_now(
            job_id=jobs[0].job_id,
            python_params=[str(document_id), uri],
        )
        return str(run.run_id)
    except Exception:
        log.exception("Failed to trigger ingest job")
        return None
