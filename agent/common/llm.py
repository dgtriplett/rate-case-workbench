"""OpenAI-compatible client pointed at Databricks Foundation Model API.

All agents share this client so that we get consistent auth + retries.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Optional

from databricks.sdk import WorkspaceClient
from openai import OpenAI

log = logging.getLogger(__name__)


def _workspace() -> WorkspaceClient:
    if os.environ.get("DATABRICKS_APP_NAME") or (
        os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN")
    ):
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
    return WorkspaceClient(profile=profile)


def _resolve_host_token() -> tuple[str, str]:
    wc = _workspace()
    host = wc.config.host or os.environ.get("DATABRICKS_HOST", "")
    if host and not host.startswith("http"):
        host = f"https://{host}"
    headers = wc.config.authenticate()
    auth = headers.get("Authorization", "")
    token = auth[len("Bearer "):] if auth.startswith("Bearer ") else (wc.config.token or "")
    return host, token


@lru_cache
def get_llm_client() -> OpenAI:
    host, token = _resolve_host_token()
    if not host or not token:
        raise RuntimeError(
            "Could not resolve Databricks host/token for OpenAI client. "
            "Set DATABRICKS_HOST + DATABRICKS_TOKEN, or DATABRICKS_PROFILE."
        )
    base_url = f"{host.rstrip('/')}/serving-endpoints"
    log.info("OpenAI client targeting %s", base_url)
    return OpenAI(api_key=token, base_url=base_url)


def chat_completion(
    model: str,
    messages: list[dict[str, Any]],
    *,
    tools: Optional[list[dict[str, Any]]] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    tool_choice: Optional[str] = None,
    response_format: Optional[dict[str, Any]] = None,
) -> Any:
    """Thin wrapper that retries once on transient errors."""
    client = get_llm_client()
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice:
            kwargs["tool_choice"] = tool_choice
    if response_format:
        kwargs["response_format"] = response_format
    try:
        return client.chat.completions.create(**kwargs)
    except Exception as e:  # pragma: no cover — retry once on transient failure
        log.warning("LLM call failed, retrying once: %s", e)
        return client.chat.completions.create(**kwargs)
