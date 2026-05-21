"""Agent runtime settings — pulls from env vars in both Model Serving and local dev.

Model Serving sets DATABRICKS_HOST + DATABRICKS_TOKEN automatically; local dev
uses ``DATABRICKS_PROFILE`` via the SDK.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class AgentSettings:
    # Models
    drafter_model: str = os.environ.get("DRAFTER_MODEL", "databricks-claude-sonnet-4-6")
    position_checker_model: str = os.environ.get(
        "POSITION_CHECKER_MODEL", "databricks-claude-sonnet-4-6"
    )
    redactor_model: str = os.environ.get("REDACTOR_MODEL", "databricks-claude-sonnet-4-6")
    summarizer_model: str = os.environ.get("SUMMARIZER_MODEL", "databricks-claude-haiku-4-5")
    memory_writer_model: str = os.environ.get(
        "MEMORY_WRITER_MODEL", "databricks-claude-sonnet-4-6"
    )
    embedding_model: str = os.environ.get("EMBEDDING_MODEL", "databricks-gte-large-en")

    # UC + Vector Search
    catalog: str = os.environ.get("UC_CATALOG", "grid_ops_demo_catalog")
    knowledge_schema: str = os.environ.get("UC_KNOWLEDGE_SCHEMA", "rcw_knowledge")
    app_schema: str = os.environ.get("UC_APP_SCHEMA", "rcw_app")
    vs_endpoint: str = os.environ.get("VS_ENDPOINT", "rcw-vs")

    # Lakebase
    pghost: str = os.environ.get("PGHOST", "")
    pgport: int = int(os.environ.get("PGPORT", "5432"))
    pgdatabase: str = os.environ.get("PGDATABASE", "databricks_postgres")
    pguser: str = os.environ.get("PGUSER", "")

    # Profile (local) — Model Serving sets DATABRICKS_HOST/TOKEN directly
    databricks_profile: str = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")

    @property
    def chunks_case_index(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.chunks_case_idx"

    @property
    def chunks_jurisdiction_index(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.chunks_jurisdiction_idx"

    @property
    def prior_responses_index(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.prior_responses_idx"

    @property
    def documents_table(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.documents"


@lru_cache
def get_agent_settings() -> AgentSettings:
    return AgentSettings()
