"""Databricks Vector Search wrapper — retrieval against the 3 indices."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from databricks.vector_search.client import VectorSearchClient

from ..config import get_settings
from ..databricks_client import get_workspace_client

log = logging.getLogger(__name__)


@dataclass
class Hit:
    document_id: str
    document_title: str
    chunk_text: str
    score: float
    page: Optional[int] = None
    case_id: Optional[str] = None
    jurisdiction: Optional[str] = None
    source_kind: Optional[str] = None
    classification: Optional[str] = None


def _client() -> VectorSearchClient:
    return VectorSearchClient(disable_notice=True)


def _search(
    index_name: str,
    query: str,
    filters: Optional[dict] = None,
    top_k: int = 8,
) -> list[Hit]:
    s = get_settings()
    try:
        client = _client()
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
        log.warning("VS search on %s failed: %s", index_name, e)
        return []

    rows = (result or {}).get("result", {}).get("data_array", [])
    cols = [c.get("name") for c in (result or {}).get("manifest", {}).get("columns", [])]
    hits: list[Hit] = []
    for r in rows:
        rec = dict(zip(cols, r))
        hits.append(
            Hit(
                document_id=rec.get("document_id", ""),
                document_title=rec.get("document_title", ""),
                chunk_text=rec.get("text", ""),
                score=float(rec.get("score", 0.0)) if "score" in rec else 0.0,
                page=rec.get("page"),
                case_id=rec.get("case_id"),
                jurisdiction=rec.get("jurisdiction"),
                source_kind=rec.get("source_kind"),
                classification=rec.get("classification"),
            )
        )
    return hits


def search_case(query: str, case_id: str, top_k: int = 8) -> list[Hit]:
    s = get_settings()
    return _search(s.chunks_case_index, query, filters={"case_id": case_id}, top_k=top_k)


def search_jurisdiction(query: str, jurisdiction: str, top_k: int = 8) -> list[Hit]:
    s = get_settings()
    return _search(
        s.chunks_jurisdiction_index, query, filters={"jurisdiction": jurisdiction}, top_k=top_k
    )


def search_prior_responses(query: str, jurisdiction: str, top_k: int = 5) -> list[Hit]:
    s = get_settings()
    return _search(
        s.prior_responses_index, query, filters={"jurisdiction": jurisdiction}, top_k=top_k
    )
