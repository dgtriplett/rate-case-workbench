"""Summarizer agent — single LLM step, called per-document during ingest."""
from __future__ import annotations

import json
import logging
from typing import Optional, TypedDict

try:
    from langgraph.graph import StateGraph, END
except ImportError:  # pragma: no cover
    StateGraph = None  # type: ignore[assignment]
    END = "__end__"

try:
    import mlflow

    trace = mlflow.trace  # type: ignore[attr-defined]
except Exception:  # pragma: no cover

    def trace(func=None, **_kw):  # type: ignore[no-redef]
        if func is None:
            return lambda f: f
        return func


from ..common.llm import chat_completion
from ..common.mlflow_log import agent_run, setup_mlflow
from ..common.settings import get_agent_settings
from .prompts import SYSTEM

log = logging.getLogger(__name__)
setup_mlflow(experiment_name="/Shared/rcw-summarizer")

_MAX_INPUT_CHARS = 24_000  # truncate front+back so the prompt fits


class SummState(TypedDict, total=False):
    title: str
    kind: str
    text: str
    model_name: str
    summary: str
    topic_tags: list[str]
    key_witnesses: list[str]
    key_numbers: list[str]


def _truncate(text: str) -> str:
    if len(text) <= _MAX_INPUT_CHARS:
        return text
    half = _MAX_INPUT_CHARS // 2
    return text[:half] + "\n\n[...truncated...]\n\n" + text[-half:]


@trace(name="summarize")
def summarize_node(state: SummState) -> SummState:
    user = (
        f"Title: {state.get('title', '(untitled)')}\n"
        f"Kind: {state.get('kind', 'unknown')}\n\n"
        f"BODY:\n{_truncate(state.get('text', ''))}\n"
    )
    resp = chat_completion(
        model=state["model_name"],
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=600,
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {}
    state["summary"] = parsed.get("summary") or ""
    state["topic_tags"] = parsed.get("topic_tags") or []
    state["key_witnesses"] = parsed.get("key_witnesses") or []
    state["key_numbers"] = parsed.get("key_numbers") or []
    return state


def build_graph():
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed in this environment")
    g = StateGraph(SummState)
    g.add_node("summarize", summarize_node)
    g.set_entry_point("summarize")
    g.add_edge("summarize", END)
    return g.compile()


def summarize_document(
    *,
    title: str,
    text: str,
    kind: str = "upload",
    model_name: Optional[str] = None,
) -> dict:
    settings = get_agent_settings()
    state: SummState = {
        "title": title,
        "kind": kind,
        "text": text,
        "model_name": model_name or settings.summarizer_model,
    }
    with agent_run(name=f"summarize::{title[:60]}"):
        out: SummState = build_graph().invoke(state)  # type: ignore[assignment]
    return {
        "summary": out.get("summary", ""),
        "topic_tags": out.get("topic_tags", []),
        "key_witnesses": out.get("key_witnesses", []),
        "key_numbers": out.get("key_numbers", []),
    }


try:
    import mlflow.pyfunc

    class SummarizerAgent(mlflow.pyfunc.PythonModel):
        def predict(self, context, model_input, params=None):  # type: ignore[override]
            import pandas as pd

            if isinstance(model_input, pd.DataFrame):
                records = model_input.to_dict(orient="records")
            elif isinstance(model_input, dict):
                records = [model_input]
            else:
                records = list(model_input)
            return [summarize_document(**rec) for rec in records]
except Exception:  # pragma: no cover

    class SummarizerAgent:  # type: ignore[no-redef]
        def predict(self, context, model_input, params=None):
            raise RuntimeError("mlflow not available")
