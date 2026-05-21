"""Position checker LangGraph agent.

The graph is small (load_memory → judge) but kept as a graph so the same
abstraction applies and MLflow's langchain autolog captures everything.
"""
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
from . import tools as pc_tools
from .prompts import SYSTEM

log = logging.getLogger(__name__)
setup_mlflow(experiment_name="/Shared/rcw-position-checker")


class PCState(TypedDict, total=False):
    case_id: str
    jurisdiction: Optional[str]
    text: str
    model_name: str
    memory: list[dict]
    warnings: list[dict]


@trace(name="load_memory")
def load_memory_node(state: PCState) -> PCState:
    state["memory"] = pc_tools.load_memory_for_case(
        state["case_id"], state.get("jurisdiction")
    )
    return state


@trace(name="judge")
def judge_node(state: PCState) -> PCState:
    memory = state.get("memory") or []
    if not memory:
        state["warnings"] = []
        return state
    payload = {
        "draft": state["text"],
        "memory": [
            {"topic_key": m.get("topic_key"), "fact_text": m.get("fact_text")}
            for m in memory
        ],
    }
    resp = chat_completion(
        model=state["model_name"],
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=1200,
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {}
    judgements = parsed.get("judgements") or []
    warnings: list[dict] = []
    by_topic = {m.get("topic_key"): m for m in memory}
    for j in judgements:
        sev = j.get("severity")
        if sev in {"info", "warning", "conflict"}:
            mem = by_topic.get(j.get("topic_key"), {})
            warnings.append(
                {
                    "topic_key": j.get("topic_key"),
                    "fact_text": j.get("fact_text") or mem.get("fact_text", ""),
                    "severity": sev,
                    "source_label": f"agent_memory#{mem.get('id', '')}",
                }
            )
    state["warnings"] = warnings
    return state


def build_graph():
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed in this environment")
    g = StateGraph(PCState)
    g.add_node("load_memory", load_memory_node)
    g.add_node("judge", judge_node)
    g.set_entry_point("load_memory")
    g.add_edge("load_memory", "judge")
    g.add_edge("judge", END)
    return g.compile()


def check_positions(
    *,
    case_id: str,
    text: str,
    jurisdiction: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    settings = get_agent_settings()
    state: PCState = {
        "case_id": case_id,
        "jurisdiction": jurisdiction,
        "text": text,
        "model_name": model_name or settings.position_checker_model,
    }
    with agent_run(name=f"position_check::{case_id[:8]}"):
        out: PCState = build_graph().invoke(state)  # type: ignore[assignment]
    return {"warnings": out.get("warnings", [])}


try:
    import mlflow.pyfunc

    class PositionCheckerAgent(mlflow.pyfunc.PythonModel):
        def predict(self, context, model_input, params=None):  # type: ignore[override]
            import pandas as pd

            if isinstance(model_input, pd.DataFrame):
                records = model_input.to_dict(orient="records")
            elif isinstance(model_input, dict):
                records = [model_input]
            else:
                records = list(model_input)
            return [check_positions(**rec) for rec in records]
except Exception:  # pragma: no cover

    class PositionCheckerAgent:  # type: ignore[no-redef]
        def predict(self, context, model_input, params=None):
            raise RuntimeError("mlflow not available")
