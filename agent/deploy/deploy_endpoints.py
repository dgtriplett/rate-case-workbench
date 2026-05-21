"""Create or update Mosaic Model Serving endpoints for each registered agent.

Usage::

    python -m agent.deploy.deploy_endpoints --agent all
    python -m agent.deploy.deploy_endpoints --agent drafter
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Optional

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import (
    EndpointCoreConfigInput,
    ServedEntityInput,
)

import mlflow

from .config import AGENTS, AgentDeployConfig, by_name

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


def _workspace() -> WorkspaceClient:
    if os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"):
        return WorkspaceClient()
    profile = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
    return WorkspaceClient(profile=profile)


def _latest_version(model: str) -> int:
    client = mlflow.MlflowClient(registry_uri="databricks-uc")
    versions = client.search_model_versions(f"name='{model}'")
    if not versions:
        raise RuntimeError(f"No registered versions for {model}")
    return max(int(v.version) for v in versions)


def deploy_endpoint(cfg: AgentDeployConfig, model_version: Optional[int] = None) -> None:
    mlflow.set_registry_uri("databricks-uc")
    version = model_version or _latest_version(cfg.registered_model)
    log.info("Deploying %s v%d → endpoint %s", cfg.registered_model, version, cfg.endpoint_name)

    w = _workspace()

    served_entity = ServedEntityInput(
        entity_name=cfg.registered_model,
        entity_version=str(version),
        workload_size=cfg.workload_size,
        scale_to_zero_enabled=cfg.scale_to_zero,
        environment_vars={
            "DRAFTER_MODEL": os.environ.get("DRAFTER_MODEL", "databricks-claude-sonnet-4-6"),
            "POSITION_CHECKER_MODEL": os.environ.get(
                "POSITION_CHECKER_MODEL", "databricks-claude-sonnet-4-6"
            ),
            "REDACTOR_MODEL": os.environ.get("REDACTOR_MODEL", "databricks-claude-sonnet-4-6"),
            "SUMMARIZER_MODEL": os.environ.get(
                "SUMMARIZER_MODEL", "databricks-claude-haiku-4-5"
            ),
            "EMBEDDING_MODEL": os.environ.get("EMBEDDING_MODEL", "databricks-gte-large-en"),
            "UC_CATALOG": os.environ.get("UC_CATALOG", "grid_ops_demo_catalog"),
            "UC_KNOWLEDGE_SCHEMA": os.environ.get("UC_KNOWLEDGE_SCHEMA", "rcw_knowledge"),
            "UC_APP_SCHEMA": os.environ.get("UC_APP_SCHEMA", "rcw_app"),
            "VS_ENDPOINT": os.environ.get("VS_ENDPOINT", "rcw-vs"),
        },
    )
    cfg_input = EndpointCoreConfigInput(
        name=cfg.endpoint_name,
        served_entities=[served_entity],
    )

    existing = None
    try:
        existing = w.serving_endpoints.get(cfg.endpoint_name)
    except Exception:
        existing = None

    if existing is None:
        log.info("Creating new endpoint %s", cfg.endpoint_name)
        w.serving_endpoints.create(name=cfg.endpoint_name, config=cfg_input)
    else:
        log.info("Updating existing endpoint %s", cfg.endpoint_name)
        w.serving_endpoints.update_config(
            name=cfg.endpoint_name, served_entities=cfg_input.served_entities
        )

    # Poll until READY
    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        ep = w.serving_endpoints.get(cfg.endpoint_name)
        state = getattr(ep.state, "ready", None) or ""
        config_update = getattr(ep.state, "config_update", None) or ""
        log.info("  state.ready=%s  config_update=%s", state, config_update)
        if str(state).upper() == "READY" and str(config_update).upper() in {"", "NOT_UPDATING"}:
            break
        time.sleep(30)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="all")
    parser.add_argument("--version", type=int, default=None)
    args = parser.parse_args()

    targets = AGENTS if args.agent == "all" else [by_name(args.agent)]
    for cfg in targets:
        deploy_endpoint(cfg, model_version=args.version)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
