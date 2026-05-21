"""Bootstrap the three Vector Search indices for the Rate Case Workbench.

Indices:
  - chunks_case_idx          (filtered by case_id)
  - chunks_jurisdiction_idx  (filtered by jurisdiction)
  - prior_responses_idx      (filtered by jurisdiction)

All three are Delta-Sync indices backed by Delta tables in
``grid_ops_demo_catalog.rcw_knowledge`` and use the
``databricks-gte-large-en`` managed embedding endpoint.
"""
from __future__ import annotations

import logging
import os
import sys
import time

from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")
log = logging.getLogger("vs-bootstrap")


ENDPOINT = os.environ.get("VS_ENDPOINT", "rcw-vs")
CATALOG = os.environ.get("CATALOG", "grid_ops_demo_catalog")
SCHEMA = os.environ.get("KNOWLEDGE_SCHEMA", "rcw_knowledge")
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "databricks-gte-large-en")


def _ensure_source_tables() -> None:
    """Create Delta source tables with the right columns if they don't exist."""
    profile = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
    w = WorkspaceClient() if os.environ.get("DATABRICKS_HOST") else WorkspaceClient(profile=profile)
    warehouse_id = os.environ.get("WAREHOUSE_ID", "7fb5ec85684023e6")

    def sql(stmt: str) -> None:
        log.info("SQL: %s", stmt.split("\n")[0][:80])
        resp = w.statement_execution.execute_statement(
            statement=stmt, warehouse_id=warehouse_id, wait_timeout="30s"
        )
        if resp.status and resp.status.state and resp.status.state.value not in ("SUCCEEDED",):
            raise RuntimeError(f"sql failed: {resp.status.error}")

    chunks_table = f"{CATALOG}.{SCHEMA}.chunks"
    sql(f"""
        CREATE TABLE IF NOT EXISTS {chunks_table} (
            id STRING NOT NULL,
            document_id STRING NOT NULL,
            chunk_index INT,
            text STRING,
            char_start INT,
            char_end INT,
            page INT,
            page_count INT,
            case_id STRING,
            jurisdiction STRING,
            document_title STRING,
            source_kind STRING,
            classification STRING
        ) USING DELTA TBLPROPERTIES (delta.enableChangeDataFeed = true)
    """)

    prior_table = f"{CATALOG}.{SCHEMA}.prior_responses"
    sql(f"""
        CREATE TABLE IF NOT EXISTS {prior_table} (
            id STRING NOT NULL,
            case_id STRING,
            jurisdiction STRING,
            dr_number STRING,
            subject STRING,
            text STRING,
            topic_tags ARRAY<STRING>,
            filed_at TIMESTAMP
        ) USING DELTA TBLPROPERTIES (delta.enableChangeDataFeed = true)
    """)


def _create_index(client: VectorSearchClient, full_name: str, source_table: str, primary_key: str = "id") -> None:
    try:
        existing = client.list_indexes(endpoint_name=ENDPOINT)
        names = {i.get("name") for i in (existing.get("vector_indexes") or [])}
    except Exception:
        names = set()
    if full_name in names:
        log.info("index %s already exists", full_name)
        return
    log.info("creating index %s", full_name)
    client.create_delta_sync_index(
        endpoint_name=ENDPOINT,
        index_name=full_name,
        source_table_name=source_table,
        pipeline_type="TRIGGERED",
        primary_key=primary_key,
        embedding_source_column="text",
        embedding_model_endpoint_name=EMBED_MODEL,
    )


def main() -> None:
    _ensure_source_tables()
    client = VectorSearchClient(disable_notice=True)
    _create_index(
        client,
        full_name=f"{CATALOG}.{SCHEMA}.chunks_case_idx",
        source_table=f"{CATALOG}.{SCHEMA}.chunks",
    )
    _create_index(
        client,
        full_name=f"{CATALOG}.{SCHEMA}.chunks_jurisdiction_idx",
        source_table=f"{CATALOG}.{SCHEMA}.chunks",
    )
    _create_index(
        client,
        full_name=f"{CATALOG}.{SCHEMA}.prior_responses_idx",
        source_table=f"{CATALOG}.{SCHEMA}.prior_responses",
    )
    log.info("done")


if __name__ == "__main__":
    main()
