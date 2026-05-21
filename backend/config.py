import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


def _coerce_int(default: int) -> int:
    raw = os.environ.get("PGPORT", "")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    pghost: str = ""
    pgport: int = 5432
    pgdatabase: str = "databricks_postgres"
    pguser: str = ""
    pgappname: str = "rate-case-workbench"

    def __init__(self, **data):
        # Resolve Lakebase env vars from any of the conventions Databricks Apps uses
        # (depends on how the database resource is bound)
        env = os.environ
        host_keys = ["PGHOST", "DATABRICKS_LAKEBASE_HOST", "DATABRICKS_DATABASE_HOST"]
        port_keys = ["PGPORT", "DATABRICKS_LAKEBASE_PORT", "DATABRICKS_DATABASE_PORT"]
        db_keys = ["PGDATABASE", "DATABRICKS_LAKEBASE_DATABASE", "DATABRICKS_DATABASE_NAME"]
        user_keys = ["PGUSER", "DATABRICKS_LAKEBASE_USER", "DATABRICKS_DATABASE_USER", "DATABRICKS_CLIENT_ID"]
        for k in host_keys:
            v = env.get(k)
            if v and "." in v:
                data.setdefault("pghost", v)
                break
        for k in port_keys:
            v = env.get(k)
            if v:
                try:
                    data.setdefault("pgport", int(v))
                    break
                except ValueError:
                    continue
        for k in db_keys:
            v = env.get(k)
            if v and "." not in v:
                data.setdefault("pgdatabase", v)
                break
        for k in user_keys:
            v = env.get(k)
            if v and "@" in v or (v and len(v) > 8 and "." not in v):
                data.setdefault("pguser", v)
                break
        super().__init__(**data)

    drafter_model: str = "databricks-claude-sonnet-4-6"
    summarizer_model: str = "databricks-claude-haiku-4-5"
    embedding_model: str = "databricks-gte-large-en"
    position_checker_model: str = "databricks-claude-sonnet-4-6"

    catalog: str = "grid_ops_demo_catalog"
    app_schema: str = "rcw_app"
    knowledge_schema: str = "rcw_knowledge"
    audit_schema: str = "rcw_audit"
    tabular_schema: str = "rcw_tabular"

    vs_endpoint: str = "rcw-vs"
    warehouse_id: str = "7fb5ec85684023e6"
    docs_volume: str = "/Volumes/grid_ops_demo_catalog/rcw_knowledge/docs_raw"
    genie_space_id: str = ""

    cors_origins: list[str] = ["*"]

    @property
    def is_databricks_app(self) -> bool:
        return bool(os.environ.get("DATABRICKS_APP_NAME"))

    @property
    def chunks_table(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.chunks"

    @property
    def documents_table(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.documents"

    @property
    def chunks_case_index(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.chunks_case_idx"

    @property
    def chunks_jurisdiction_index(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.chunks_jurisdiction_idx"

    @property
    def prior_responses_index(self) -> str:
        return f"{self.catalog}.{self.knowledge_schema}.prior_responses_idx"


@lru_cache
def get_settings() -> Settings:
    return Settings()
