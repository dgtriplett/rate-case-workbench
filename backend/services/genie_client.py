"""Genie API client — query a Genie space and return a structured result."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..databricks_client import get_oauth_token, get_workspace_host

log = logging.getLogger(__name__)


@dataclass
class GenieResult:
    question: str
    sql: Optional[str]
    columns: list[str]
    rows: list[list[Any]]
    explanation: Optional[str]
    space_id: str
    conversation_id: Optional[str]
    message_id: Optional[str]


async def ask(question: str, space_id: str, timeout_seconds: int = 90) -> GenieResult:
    host = get_workspace_host()
    token = get_oauth_token()
    base = f"{host}/api/2.0/genie/spaces/{space_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{base}/start-conversation",
            json={"content": question},
            headers=headers,
        )
        r.raise_for_status()
        data = r.json()
        conversation_id = data.get("conversation_id") or data.get("conversation", {}).get("id")
        message_id = data.get("message_id") or data.get("message", {}).get("id")

        end = time.time() + timeout_seconds
        attachment = None
        explanation = None
        while time.time() < end:
            mr = await client.get(
                f"{base}/conversations/{conversation_id}/messages/{message_id}",
                headers=headers,
            )
            mr.raise_for_status()
            msg = mr.json()
            status = msg.get("status")
            if status in ("COMPLETED", "FAILED", "CANCELLED"):
                attachment = (msg.get("attachments") or [None])[0]
                explanation = msg.get("content")
                break
            await asyncio.sleep(2)

        if not attachment:
            return GenieResult(
                question=question,
                sql=None,
                columns=[],
                rows=[],
                explanation=explanation or "no result",
                space_id=space_id,
                conversation_id=conversation_id,
                message_id=message_id,
            )

        sql = (attachment.get("query") or {}).get("query")
        attachment_id = attachment.get("attachment_id") or attachment.get("id")
        qr = await client.get(
            f"{base}/conversations/{conversation_id}/messages/{message_id}/attachments/{attachment_id}/query-result",
            headers=headers,
        )
        qr.raise_for_status()
        qdata = qr.json()
        manifest = qdata.get("statement_response", {}).get("manifest", {}).get("schema", {})
        cols = [c.get("name") for c in manifest.get("columns", [])]
        rows = qdata.get("statement_response", {}).get("result", {}).get("data_array", [])

        return GenieResult(
            question=question,
            sql=sql,
            columns=cols,
            rows=rows,
            explanation=explanation,
            space_id=space_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )
