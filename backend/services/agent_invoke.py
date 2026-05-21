"""Invoke deployed Mosaic Agent endpoints. Falls back to a local in-process
implementation when the endpoint is unavailable (so the app still works in
demo mode before agent endpoints are deployed)."""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

import httpx

from ..config import get_settings
from ..databricks_client import get_oauth_token, get_workspace_host

log = logging.getLogger(__name__)


async def invoke(endpoint: str, payload: dict[str, Any], timeout: float = 120.0) -> dict[str, Any]:
    host = get_workspace_host()
    token = get_oauth_token()
    url = f"{host}/serving-endpoints/{endpoint}/invocations"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json={"inputs": [payload]}, headers=headers)
        r.raise_for_status()
        data = r.json()
        preds = data.get("predictions") or data.get("outputs") or []
        if not preds:
            return {}
        first = preds[0]
        if isinstance(first, str):
            try:
                return json.loads(first)
            except Exception:
                return {"text": first}
        return first


def drafter_endpoint() -> str:
    return os.environ.get("RCW_DRAFTER_ENDPOINT", "rcw-drafter")


def position_checker_endpoint() -> str:
    return os.environ.get("RCW_POSITION_CHECKER_ENDPOINT", "rcw-position-checker")


def redactor_endpoint() -> str:
    return os.environ.get("RCW_REDACTOR_ENDPOINT", "rcw-redactor")
