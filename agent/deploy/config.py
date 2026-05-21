"""Central deploy config — agent registry shared by register/deploy scripts."""
from __future__ import annotations

import os
from dataclasses import dataclass


CATALOG = os.environ.get("UC_CATALOG", "grid_ops_demo_catalog")
APP_SCHEMA = os.environ.get("UC_APP_SCHEMA", "rcw_app")


@dataclass(frozen=True)
class AgentDeployConfig:
    name: str                      # short name (e.g. "drafter")
    endpoint_name: str             # Model Serving endpoint name (e.g. "rcw-drafter")
    registered_model: str          # full UC name catalog.schema.name
    model_class_import: str        # "agent.drafter.agent:DrafterAgent"
    experiment: str                # MLflow experiment path
    pip_requirements: list[str]
    input_example: dict
    workload_size: str = "Small"
    scale_to_zero: bool = True


_BASE_REQS = [
    "openai>=1.52.0",
    "databricks-sdk>=0.40.0",
    "databricks-vectorsearch>=0.40",
    "mlflow>=2.18.0",
    "langgraph>=0.2.50",
    "langchain-core>=0.3.0",
    "pydantic>=2.7.0",
    "httpx>=0.27.0",
    "asyncpg>=0.29.0",
    "sqlalchemy[asyncio]>=2.0.30",
]


AGENTS: list[AgentDeployConfig] = [
    AgentDeployConfig(
        name="drafter",
        endpoint_name="rcw-drafter",
        registered_model=f"{CATALOG}.{APP_SCHEMA}.drafter",
        model_class_import="agent.drafter.agent:DrafterAgent",
        experiment="/Shared/rcw-drafter",
        pip_requirements=_BASE_REQS,
        input_example={
            "case_id": "00000000-0000-0000-0000-000000000000",
            "jurisdiction": "State of Cascadia",
            "dr_number": "NLPG-26-001-DR-001",
            "dr_subject": "Provide 5-year O&M growth by function",
            "dr_body": "Please provide…",
            "requester": "CPUC-X Staff",
            "requester_kind": "staff",
            "user_instruction": None,
            "extra_context": None,
            "genie_room_id": None,
            "model_name": None,
        },
        workload_size="Small",
        scale_to_zero=True,
    ),
    AgentDeployConfig(
        name="position_checker",
        endpoint_name="rcw-position-checker",
        registered_model=f"{CATALOG}.{APP_SCHEMA}.position_checker",
        model_class_import="agent.position_checker.agent:PositionCheckerAgent",
        experiment="/Shared/rcw-position-checker",
        pip_requirements=_BASE_REQS,
        input_example={
            "case_id": "00000000-0000-0000-0000-000000000000",
            "text": "The Company proposes an ROE of 9.85%…",
            "jurisdiction": "State of Cascadia",
        },
        workload_size="Small",
        scale_to_zero=True,
    ),
    AgentDeployConfig(
        name="redactor",
        endpoint_name="rcw-redactor",
        registered_model=f"{CATALOG}.{APP_SCHEMA}.redactor",
        model_class_import="agent.redactor.agent:RedactorAgent",
        experiment="/Shared/rcw-redactor",
        pip_requirements=_BASE_REQS,
        input_example={
            "text": "Sample response text to redact for PII and privilege.",
        },
        workload_size="Small",
        scale_to_zero=True,
    ),
    AgentDeployConfig(
        name="summarizer",
        endpoint_name="rcw-summarizer",
        registered_model=f"{CATALOG}.{APP_SCHEMA}.summarizer",
        model_class_import="agent.summarizer.agent:SummarizerAgent",
        experiment="/Shared/rcw-summarizer",
        pip_requirements=_BASE_REQS,
        input_example={
            "title": "Direct Testimony of Maria Calderón",
            "text": "...sample text...",
            "kind": "testimony",
        },
        workload_size="Small",
        scale_to_zero=True,
    ),
]


def by_name(name: str) -> AgentDeployConfig:
    for a in AGENTS:
        if a.name == name:
            return a
    raise KeyError(name)
