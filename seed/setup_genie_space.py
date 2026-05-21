"""Programmatically create or update the ``rcw-evidence-genie`` Genie space.

Uses the Databricks Genie REST API (``POST /api/2.0/genie/spaces``). The API
takes a ``serialized_space`` payload conforming to the public GenieSpaceExport
proto (version 2). Tables are referenced by their fully-qualified
``catalog.schema.table`` identifier, sorted alphabetically.

Writes the resulting space ID to ``seed/output/genie_space_id.txt`` and prints
it. ``seed_db.py`` reads this file (or the ``GENIE_SPACE_ID`` env var) to
upsert a row in the ``genie_rooms`` table so the app can register the space.

Usage::

    DATABRICKS_PROFILE=fe-vm-grid-ops-demo python -m seed.setup_genie_space
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import httpx

try:
    _SCRIPT_ROOT = Path(__file__).resolve().parent.parent
except NameError:
    _SCRIPT_ROOT = Path(
        os.environ.get(
            "RCW_PROJECT_ROOT",
            "/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench",
        )
    )
ROOT = _SCRIPT_ROOT
sys.path.insert(0, str(ROOT))

from backend.databricks_client import get_oauth_token, get_workspace_host  # noqa: E402

log = logging.getLogger("setup_genie")
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


CATALOG = os.environ.get("UC_CATALOG", "grid_ops_demo_catalog")
TABULAR_SCHEMA = os.environ.get("UC_TABULAR_SCHEMA", "rcw_tabular")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "7fb5ec85684023e6")
SPACE_TITLE = os.environ.get("GENIE_SPACE_TITLE", "rcw-evidence-genie")

OUTPUT_DIR = ROOT / "seed" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
SPACE_ID_FILE = OUTPUT_DIR / "genie_space_id.txt"

# Must be sorted alphabetically by identifier (Genie proto requirement).
TABLES = sorted([
    f"{CATALOG}.{TABULAR_SCHEMA}.billing_determinants",
    f"{CATALOG}.{TABULAR_SCHEMA}.capex_plan",
    f"{CATALOG}.{TABULAR_SCHEMA}.customer_counts",
    f"{CATALOG}.{TABULAR_SCHEMA}.om_expenses",
    f"{CATALOG}.{TABULAR_SCHEMA}.rate_base",
    f"{CATALOG}.{TABULAR_SCHEMA}.roe_history",
])


DESCRIPTION = (
    "Tabular evidence for the Rate Case Workbench. "
    "rate_base, O&M, capex, customer counts, billing determinants, and ROE "
    "history — all values in $M unless noted; ROE stored as raw percent. "
    "Use CAGR 2020 to 2025 for 5-year growth questions."
)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_oauth_token()}",
        "Content-Type": "application/json",
    }


def _serialized_space() -> str:
    payload = {
        "version": 2,
        "data_sources": {
            "tables": [{"identifier": t} for t in TABLES],
        },
    }
    return json.dumps(payload)


def _find_existing(client: httpx.Client, host: str) -> str | None:
    try:
        r = client.get(f"{host}/api/2.0/genie/spaces", headers=_headers())
        if r.status_code != 200:
            return None
        for sp in (r.json() or {}).get("spaces", []) or []:
            if sp.get("title") == SPACE_TITLE:
                return sp.get("space_id") or sp.get("id")
    except Exception as e:
        log.warning("could not list Genie spaces: %s", e)
    return None


def create_or_update() -> str:
    host = get_workspace_host().rstrip("/")
    body = {
        "warehouse_id": WAREHOUSE_ID,
        "title": SPACE_TITLE,
        "description": DESCRIPTION,
        "serialized_space": _serialized_space(),
    }
    with httpx.Client(timeout=60) as client:
        existing = _find_existing(client, host)
        if existing:
            log.info("Existing Genie space %s — leaving in place", existing)
            return existing
        log.info("Creating Genie space %r with %d tables", SPACE_TITLE, len(TABLES))
        r = client.post(
            f"{host}/api/2.0/genie/spaces", headers=_headers(), json=body
        )
        if r.status_code >= 400:
            raise RuntimeError(f"create failed: {r.status_code} {r.text}")
        data = r.json()
        space_id = data.get("space_id") or data.get("id")
        if not space_id:
            raise RuntimeError(f"unexpected response: {data}")
        return space_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-only", action="store_true")
    parser.parse_args()
    space_id = create_or_update()
    SPACE_ID_FILE.write_text(space_id)
    print(space_id)
    log.info("Genie space ID: %s (written to %s)", space_id, SPACE_ID_FILE)
    return 0


if __name__ == "__main__":  # pragma: no cover
    rc = main()
    if rc:
        raise SystemExit(rc)
