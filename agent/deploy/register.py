"""Log + register a single agent to MLflow UC Model Registry.

Usage::

    python -m agent.deploy.register --agent drafter
    python -m agent.deploy.register --agent all
"""
from __future__ import annotations

import argparse
import importlib
import logging
import sys
from pathlib import Path

import mlflow
from mlflow.models.signature import infer_signature

from .config import AGENTS, AgentDeployConfig, by_name

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_model_class(import_path: str):
    module_path, _, class_name = import_path.partition(":")
    mod = importlib.import_module(module_path)
    return getattr(mod, class_name)


def _example_output_for(name: str) -> dict | list:
    if name == "drafter":
        return {
            "draft_text": "",
            "citations": [],
            "steps": [],
            "agent_trace_id": None,
            "model_version": None,
            "position_warnings": [],
        }
    if name == "position_checker":
        return {"warnings": []}
    if name == "redactor":
        return {"spans": [], "summary": ""}
    if name == "summarizer":
        return {
            "summary": "",
            "topic_tags": [],
            "key_witnesses": [],
            "key_numbers": [],
        }
    return {}


def register_agent(cfg: AgentDeployConfig) -> str:
    """Log + register the agent. Returns the new model version URI."""
    mlflow.set_tracking_uri("databricks")
    mlflow.set_registry_uri("databricks-uc")
    mlflow.set_experiment(cfg.experiment)

    ModelCls = _resolve_model_class(cfg.model_class_import)
    log.info("Logging agent %s …", cfg.name)

    input_example = cfg.input_example
    output_example = _example_output_for(cfg.name)
    signature = infer_signature(input_example, output_example)

    with mlflow.start_run(run_name=f"register::{cfg.name}") as run:
        mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=ModelCls(),
            signature=signature,
            input_example=input_example,
            pip_requirements=cfg.pip_requirements,
            code_path=[
                str(_PROJECT_ROOT / "agent"),
            ],
            registered_model_name=cfg.registered_model,
        )
        run_id = run.info.run_id

    client = mlflow.MlflowClient(registry_uri="databricks-uc")
    versions = client.search_model_versions(f"name='{cfg.registered_model}'")
    latest = max(int(v.version) for v in versions) if versions else 1
    log.info("Registered %s as version %d (run %s)", cfg.registered_model, latest, run_id)
    return f"models:/{cfg.registered_model}/{latest}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent", default="all", help="agent name or 'all'")
    args = parser.parse_args()

    targets = AGENTS if args.agent == "all" else [by_name(args.agent)]
    for cfg in targets:
        uri = register_agent(cfg)
        log.info("→ %s URI: %s", cfg.name, uri)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
