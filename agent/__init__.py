"""Mosaic AI agents for the Rate Case Workbench.

Sub-packages:
    drafter           — hero LangGraph agent that drafts data-request responses
    position_checker  — flags contradictions vs stored positions
    redactor          — scans drafts for PII / privileged language
    summarizer        — summarizes uploaded docs for the ingest pipeline
    memory_writer     — Databricks Job that mines approved responses into agent_memory
    deploy            — MLflow registration + Model Serving deploy scripts
"""

__all__ = [
    "drafter",
    "position_checker",
    "redactor",
    "summarizer",
    "memory_writer",
    "deploy",
]
