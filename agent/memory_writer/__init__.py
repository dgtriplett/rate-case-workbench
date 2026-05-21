"""Memory writer — Databricks Job that mines approved responses into agent_memory.

Not deployed as a Model Serving endpoint. Run via ``python -m agent.memory_writer.job``.
"""
from .job import run_memory_writer, extract_positions

__all__ = ["run_memory_writer", "extract_positions"]
