"""Tool functions for the drafter agent.

Each tool is decorated with ``@mlflow.trace`` so its inputs/outputs land in the
MLflow trace tree alongside the LLM calls (autologged via ``mlflow.langchain``).
The tools also expose OpenAI tool-spec dicts (``TOOL_SPECS``) for the
function-calling step in agent.py.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import asdict
from typing import Any, Optional

import httpx

try:
    import mlflow

    trace = mlflow.trace  # type: ignore[attr-defined]
except Exception:  # pragma: no cover

    def trace(func=None, **_kw):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func


from databricks.vector_search.client import VectorSearchClient
from sqlalchemy import text

from ..common.lakebase import session_scope
from ..common.llm import _resolve_host_token
from ..common.settings import get_agent_settings

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Vector Search
# ---------------------------------------------------------------------------


def _vs_client() -> VectorSearchClient:
    return VectorSearchClient(disable_notice=True)


def _vs_search(index_name: str, query: str, filters: Optional[dict], top_k: int) -> list[dict]:
    s = get_agent_settings()
    try:
        client = _vs_client()
        index = client.get_index(endpoint_name=s.vs_endpoint, index_name=index_name)
        result = index.similarity_search(
            query_text=query,
            columns=[
                "document_id",
                "document_title",
                "text",
                "page",
                "case_id",
                "jurisdiction",
                "source_kind",
                "classification",
            ],
            num_results=top_k,
            filters=filters,
        )
    except Exception as e:
        log.warning("VS search failed on %s: %s", index_name, e)
        return []

    rows = (result or {}).get("result", {}).get("data_array", []) or []
    cols = [c.get("name") for c in (result or {}).get("manifest", {}).get("columns", [])]
    return [dict(zip(cols, r)) for r in rows]


@trace(name="vs_search_case")
def vs_search_case(query: str, case_id: str, top_k: int = 8) -> list[dict]:
    """Search the case-scoped chunks index, filtered by case_id."""
    s = get_agent_settings()
    return _vs_search(s.chunks_case_index, query, {"case_id": case_id}, top_k)


@trace(name="vs_search_jurisdiction")
def vs_search_jurisdiction(query: str, jurisdiction: str, top_k: int = 8) -> list[dict]:
    """Search the jurisdiction-prior-case chunks index, filtered by jurisdiction."""
    s = get_agent_settings()
    return _vs_search(s.chunks_jurisdiction_index, query, {"jurisdiction": jurisdiction}, top_k)


@trace(name="vs_search_prior_responses")
def vs_search_prior_responses(query: str, jurisdiction: str, top_k: int = 5) -> list[dict]:
    """Search the prior-responses index, filtered by jurisdiction."""
    s = get_agent_settings()
    return _vs_search(s.prior_responses_index, query, {"jurisdiction": jurisdiction}, top_k)


# ---------------------------------------------------------------------------
# Lakebase agent_memory + documents
# ---------------------------------------------------------------------------


async def _read_memory_async(
    case_id: Optional[str], jurisdiction: Optional[str], topic_keys: Optional[list[str]]
) -> list[dict]:
    async with session_scope() as sess:
        sql = (
            "SELECT id::text, case_id::text, jurisdiction, topic_key, fact_text, "
            "rationale, confidence, is_active "
            "FROM agent_memory "
            "WHERE is_active = TRUE "
            "AND (case_id = CAST(:case_id AS uuid) OR jurisdiction = :jurisdiction) "
        )
        params: dict[str, Any] = {"case_id": case_id, "jurisdiction": jurisdiction}
        if topic_keys:
            sql += "AND topic_key = ANY(:topic_keys) "
            params["topic_keys"] = topic_keys
        sql += "ORDER BY confidence DESC, created_at DESC LIMIT 50"
        res = await sess.execute(text(sql), params)
        rows = res.mappings().all()
        return [dict(r) for r in rows]


@trace(name="read_memory")
def read_memory(
    case_id: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    topic_keys: Optional[list[str]] = None,
) -> list[dict]:
    """Read active agent_memory rows scoped to the case or jurisdiction."""
    if not case_id and not jurisdiction:
        return []
    try:
        return asyncio.run(_read_memory_async(case_id, jurisdiction, topic_keys))
    except RuntimeError:
        # Already inside a running loop (e.g. inside FastAPI). Use new loop.
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(
                _read_memory_async(case_id, jurisdiction, topic_keys)
            )
        finally:
            loop.close()


async def _cite_document_async(document_id: str) -> Optional[dict]:
    async with session_scope() as sess:
        res = await sess.execute(
            text(
                "SELECT id::text, title, kind, uri, page_count, classification, "
                "summary, topic_tags FROM documents WHERE id = CAST(:id AS uuid)"
            ),
            {"id": document_id},
        )
        row = res.mappings().first()
        return dict(row) if row else None


@trace(name="cite_document")
def cite_document(document_id: str) -> Optional[dict]:
    """Return doc metadata for inline citation."""
    try:
        return asyncio.run(_cite_document_async(document_id))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_cite_document_async(document_id))
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Genie
# ---------------------------------------------------------------------------


_GENIE_TIMEOUT = 90
_GENIE_POLL_INTERVAL = 2.0


@trace(name="query_genie")
def query_genie(question: str, room_id: str) -> dict:
    """Pose a natural-language question to a Genie room and return the table preview.

    Returns ``{"sql": "...", "columns": [...], "rows": [...], "row_count": N, "message": "..."}``.
    """
    if not room_id:
        return {"error": "no room_id"}
    host, token = _resolve_host_token()
    base = f"{host.rstrip('/')}/api/2.0/genie/spaces/{room_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    with httpx.Client(timeout=30) as client:
        # 1) Start a conversation message
        r = client.post(
            f"{base}/start-conversation",
            headers=headers,
            json={"content": question},
        )
        r.raise_for_status()
        start = r.json()
        conv_id = start.get("conversation_id") or start.get("conversation", {}).get("id")
        msg_id = start.get("message_id") or start.get("message", {}).get("id")
        if not conv_id or not msg_id:
            return {"error": "could not start Genie conversation", "raw": start}

        # 2) Poll until status is COMPLETED or FAILED
        deadline = time.time() + _GENIE_TIMEOUT
        message: dict[str, Any] = {}
        while time.time() < deadline:
            mr = client.get(
                f"{base}/conversations/{conv_id}/messages/{msg_id}", headers=headers
            )
            mr.raise_for_status()
            message = mr.json()
            status = message.get("status") or message.get("state") or ""
            if status in {"COMPLETED", "FAILED", "CANCELLED"}:
                break
            time.sleep(_GENIE_POLL_INTERVAL)

        attachments = message.get("attachments") or []
        out: dict[str, Any] = {"message": message.get("content"), "row_count": 0}
        for att in attachments:
            q = att.get("query") or {}
            if q.get("query"):
                out["sql"] = q.get("query")
            if att.get("text"):
                out["message"] = att.get("text", {}).get("content") or out.get("message")

        # 3) Fetch the first attachment's result rows (preview)
        for att in attachments:
            att_id = att.get("attachment_id") or att.get("id")
            if not att_id or not att.get("query"):
                continue
            try:
                qr = client.get(
                    f"{base}/conversations/{conv_id}/messages/{msg_id}/attachments/{att_id}/query-result",
                    headers=headers,
                )
                qr.raise_for_status()
                data = qr.json().get("statement_response", {}) or qr.json()
                manifest = data.get("manifest", {}) or {}
                cols = [c.get("name") for c in (manifest.get("schema", {}).get("columns") or [])]
                result = data.get("result", {}) or {}
                rows_raw = result.get("data_array") or []
                preview = rows_raw[:20]
                out["columns"] = cols
                out["rows"] = preview
                out["row_count"] = int(result.get("row_count") or len(rows_raw))
            except Exception as e:
                log.warning("Genie result fetch failed: %s", e)
            break

        return out


# ---------------------------------------------------------------------------
# OpenAI tool specs (function-calling)
# ---------------------------------------------------------------------------


TOOLS = {
    "vs_search_case": vs_search_case,
    "vs_search_jurisdiction": vs_search_jurisdiction,
    "vs_search_prior_responses": vs_search_prior_responses,
    "read_memory": read_memory,
    "query_genie": query_genie,
    "cite_document": cite_document,
}


TOOL_SPECS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "vs_search_case",
            "description": "Semantic search over filings, exhibits, and testimony scoped to the current case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "case_id": {"type": "string"},
                    "top_k": {"type": "integer", "default": 8},
                },
                "required": ["query", "case_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vs_search_jurisdiction",
            "description": "Semantic search over prior cases and orders in the same jurisdiction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "jurisdiction": {"type": "string"},
                    "top_k": {"type": "integer", "default": 8},
                },
                "required": ["query", "jurisdiction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vs_search_prior_responses",
            "description": "Semantic search over prior approved/filed data-request responses in the jurisdiction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "jurisdiction": {"type": "string"},
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query", "jurisdiction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_memory",
            "description": "Read agent_memory rows (stored positions) for this case or jurisdiction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "case_id": {"type": "string"},
                    "jurisdiction": {"type": "string"},
                    "topic_keys": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_genie",
            "description": (
                "Ask the Genie data-analyst room a natural-language question over the rate-case tabular evidence. "
                "Returns SQL + a preview of the result rows."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "room_id": {"type": "string"},
                },
                "required": ["question", "room_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cite_document",
            "description": "Return the title, kind, uri, and metadata for a document_id (for citation building).",
            "parameters": {
                "type": "object",
                "properties": {"document_id": {"type": "string"}},
                "required": ["document_id"],
            },
        },
    },
]
