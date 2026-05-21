"""Foundation Model API client — used by routers for one-shot LLM calls (the agent endpoint handles complex flows)."""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from openai import AsyncOpenAI

from ..config import get_settings
from ..databricks_client import get_oauth_token, get_workspace_host

log = logging.getLogger(__name__)


@lru_cache
def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=get_oauth_token(), base_url=f"{get_workspace_host()}/serving-endpoints")


async def chat(messages: list[dict[str, Any]], model: str | None = None, **kw) -> str:
    s = get_settings()
    client = _client()
    resp = await client.chat.completions.create(
        model=model or s.drafter_model,
        messages=messages,
        max_tokens=kw.pop("max_tokens", 2048),
        temperature=kw.pop("temperature", 0.4),
        **kw,
    )
    return resp.choices[0].message.content or ""
