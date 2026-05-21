"""Redactor LangGraph agent — single-step LLM scan."""
from __future__ import annotations

import json
import logging
import re
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
setup_mlflow(experiment_name="/Shared/rcw-redactor")

# Quick deterministic backstops (LLM is primary detector)
_REGEX_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "pii", "ssn", "[REDACTED-SSN]"),
    (re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b"), "pii", "phone", "[REDACTED-PHONE]"),
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@(?!nlpg\.com|databricks\.com)[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "pii",
        "email",
        "[REDACTED-EMAIL]",
    ),
    (
        re.compile(r"\b(attorney[- ]client|privileged\s*(and|&)\s*confidential)\b", re.IGNORECASE),
        "privileged",
        "marker",
        "[REDACTED-PRIVILEGED]",
    ),
]


class RedactorState(TypedDict, total=False):
    text: str
    model_name: str
    spans: list[dict]
    summary: str


@trace(name="regex_scan")
def regex_scan_node(state: RedactorState) -> RedactorState:
    spans: list[dict] = []
    for pat, kind, subtype, suggestion in _REGEX_PATTERNS:
        for m in pat.finditer(state["text"]):
            spans.append(
                {
                    "start": m.start(),
                    "end": m.end(),
                    "kind": kind,
                    "subtype": subtype,
                    "snippet": m.group(0),
                    "suggestion": suggestion,
                    "source": "regex",
                }
            )
    state["spans"] = spans
    return state


@trace(name="llm_scan")
def llm_scan_node(state: RedactorState) -> RedactorState:
    resp = chat_completion(
        model=state["model_name"],
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": state["text"]},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=1200,
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {"spans": [], "summary": "LLM response unparseable"}
    llm_spans = parsed.get("spans") or []
    for s in llm_spans:
        s.setdefault("source", "llm")
    state["spans"] = (state.get("spans") or []) + llm_spans
    state["summary"] = parsed.get("summary") or f"Found {len(state['spans'])} issue(s)"
    # Dedupe by (start, end, kind)
    seen = set()
    deduped: list[dict] = []
    for s in state["spans"]:
        k = (s.get("start"), s.get("end"), s.get("kind"))
        if k in seen:
            continue
        seen.add(k)
        deduped.append(s)
    state["spans"] = deduped
    return state


def build_graph():
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed in this environment")
    g = StateGraph(RedactorState)
    g.add_node("regex_scan", regex_scan_node)
    g.add_node("llm_scan", llm_scan_node)
    g.set_entry_point("regex_scan")
    g.add_edge("regex_scan", "llm_scan")
    g.add_edge("llm_scan", END)
    return g.compile()


def redact_text(*, text: str, model_name: Optional[str] = None) -> dict:
    settings = get_agent_settings()
    state: RedactorState = {
        "text": text,
        "model_name": model_name or settings.redactor_model,
    }
    with agent_run(name="redact"):
        out: RedactorState = build_graph().invoke(state)  # type: ignore[assignment]
    return {"spans": out.get("spans", []), "summary": out.get("summary", "")}


try:
    import mlflow.pyfunc

    class RedactorAgent(mlflow.pyfunc.PythonModel):
        def predict(self, context, model_input, params=None):  # type: ignore[override]
            import pandas as pd

            if isinstance(model_input, pd.DataFrame):
                records = model_input.to_dict(orient="records")
            elif isinstance(model_input, dict):
                records = [model_input]
            else:
                records = list(model_input)
            return [redact_text(**rec) for rec in records]
except Exception:  # pragma: no cover

    class RedactorAgent:  # type: ignore[no-redef]
        def predict(self, context, model_input, params=None):
            raise RuntimeError("mlflow not available")
