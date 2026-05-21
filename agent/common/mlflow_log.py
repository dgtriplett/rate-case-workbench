"""MLflow tracing helpers — every agent calls ``setup_mlflow()`` at import time
so traces, autologs, and run IDs are consistently captured.
"""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator, Optional

log = logging.getLogger(__name__)

_INITIALIZED = False


def setup_mlflow(experiment_name: Optional[str] = None) -> None:
    """Idempotent MLflow setup. Picks up Databricks tracking URI in app + Model Serving."""
    global _INITIALIZED
    if _INITIALIZED:
        return
    try:
        import mlflow

        # Default tracking URI = "databricks" when running in workspace
        if not os.environ.get("MLFLOW_TRACKING_URI"):
            try:
                mlflow.set_tracking_uri("databricks")
            except Exception:
                pass

        if experiment_name:
            try:
                mlflow.set_experiment(experiment_name)
            except Exception as e:
                log.warning("Could not set experiment %s: %s", experiment_name, e)

        # Autolog langchain / openai so tools + LLM calls show up in MLflow traces
        try:
            mlflow.langchain.autolog()
        except Exception:
            pass
        try:
            mlflow.openai.autolog()
        except Exception:
            pass

        _INITIALIZED = True
    except Exception as e:  # pragma: no cover
        log.warning("MLflow setup skipped: %s", e)


@contextmanager
def agent_run(name: str) -> Iterator[Optional[str]]:
    """Yield the active MLflow run id (or None if MLflow unavailable)."""
    try:
        import mlflow

        with mlflow.start_run(run_name=name, nested=mlflow.active_run() is not None) as run:
            yield run.info.run_id
    except Exception:
        yield None
