"""Drafter LangGraph state graph.

Nodes:
    plan        — LLM produces a JSON plan of searches + Genie call
    retrieve    — executes case/jurisdiction/prior-response VS searches
    memory      — reads agent_memory for the topics in the plan
    genie       — optional tabular call
    draft       — LLM writes the response using all gathered evidence
    critique    — self-critique against memory facts; emits position_warnings
    finalize    — assemble DraftResult (text + citations + steps + warnings)

The graph is built with ``langgraph.StateGraph`` and uses an explicit TypedDict
state so MLflow's langchain autolog captures everything.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Optional, TypedDict

try:
    from langgraph.graph import StateGraph, END
except ImportError:  # pragma: no cover — defer import for environments without langgraph
    StateGraph = None  # type: ignore[assignment]
    END = "__end__"  # type: ignore[assignment]

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
from . import tools as drafter_tools
from .prompts import CRITIQUE_SYSTEM, DRAFT_SYSTEM, PLAN_SYSTEM

log = logging.getLogger(__name__)

setup_mlflow(experiment_name="/Shared/rcw-drafter")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class DrafterState(TypedDict, total=False):
    # Inputs
    case_id: str
    jurisdiction: str
    dr_number: str
    dr_subject: str
    dr_body: str
    requester: str
    requester_kind: Optional[str]
    user_instruction: Optional[str]
    extra_context: Optional[str]
    genie_room_id: Optional[str]
    model_name: str

    # Working scratch
    plan: dict[str, Any]
    case_hits: list[dict]
    jurisdiction_hits: list[dict]
    prior_response_hits: list[dict]
    memory_hits: list[dict]
    genie_result: Optional[dict]

    # Outputs
    draft_text: str
    citations: list[dict]
    steps: list[dict]
    position_warnings: list[str]
    agent_trace_id: Optional[str]
    model_version: Optional[str]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def _append_step(state: DrafterState, kind: str, label: str, detail: Optional[str] = None) -> None:
    state.setdefault("steps", []).append({"kind": kind, "label": label, "detail": detail})


@trace(name="plan_node")
def plan_node(state: DrafterState) -> DrafterState:
    user_msg = json.dumps(
        {
            "subject": state.get("dr_subject"),
            "body": state.get("dr_body"),
            "requester": state.get("requester"),
            "requester_kind": state.get("requester_kind"),
            "case_id": state.get("case_id"),
            "jurisdiction": state.get("jurisdiction"),
            "user_instruction": state.get("user_instruction"),
        }
    )
    resp = chat_completion(
        model=state["model_name"],
        messages=[
            {"role": "system", "content": PLAN_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=800,
    )
    content = resp.choices[0].message.content or "{}"
    try:
        plan = json.loads(content)
    except json.JSONDecodeError:
        log.warning("Plan JSON malformed; using fallback plan")
        plan = {
            "intent": state.get("dr_subject", ""),
            "search_queries": [
                {"scope": "case", "query": state.get("dr_subject", "")},
            ],
            "needs_genie": False,
            "memory_topics": [],
        }
    state["plan"] = plan
    _append_step(state, "plan", "Planned retrieval", json.dumps(plan)[:600])
    return state


@trace(name="retrieve_node")
def retrieve_node(state: DrafterState) -> DrafterState:
    plan = state.get("plan", {}) or {}
    queries = plan.get("search_queries") or [
        {"scope": "case", "query": state.get("dr_subject", "")}
    ]
    case_hits: list[dict] = []
    jur_hits: list[dict] = []
    prior_hits: list[dict] = []
    for q in queries:
        scope = q.get("scope", "case")
        qry = q.get("query") or state.get("dr_subject", "")
        if scope == "case" and state.get("case_id"):
            case_hits.extend(drafter_tools.vs_search_case(qry, state["case_id"], top_k=8))
        elif scope == "jurisdiction" and state.get("jurisdiction"):
            jur_hits.extend(
                drafter_tools.vs_search_jurisdiction(qry, state["jurisdiction"], top_k=6)
            )
        elif scope == "prior_responses" and state.get("jurisdiction"):
            prior_hits.extend(
                drafter_tools.vs_search_prior_responses(qry, state["jurisdiction"], top_k=5)
            )
    # Always include a jurisdiction sweep on the DR subject, so prior orders surface.
    if state.get("jurisdiction") and not jur_hits:
        jur_hits.extend(
            drafter_tools.vs_search_jurisdiction(state.get("dr_subject", ""), state["jurisdiction"], top_k=4)
        )
    state["case_hits"] = case_hits
    state["jurisdiction_hits"] = jur_hits
    state["prior_response_hits"] = prior_hits
    _append_step(
        state,
        "retrieval",
        f"Retrieved {len(case_hits)} case / {len(jur_hits)} jurisdiction / {len(prior_hits)} prior-response chunks",
    )
    return state


@trace(name="memory_node")
def memory_node(state: DrafterState) -> DrafterState:
    topics = (state.get("plan") or {}).get("memory_topics") or None
    rows = drafter_tools.read_memory(
        case_id=state.get("case_id"),
        jurisdiction=state.get("jurisdiction"),
        topic_keys=topics,
    )
    state["memory_hits"] = rows
    _append_step(state, "memory", f"Loaded {len(rows)} memory rows", json.dumps([r.get("topic_key") for r in rows])[:400])
    return state


@trace(name="genie_node")
def genie_node(state: DrafterState) -> DrafterState:
    plan = state.get("plan") or {}
    if not plan.get("needs_genie") or not state.get("genie_room_id"):
        state["genie_result"] = None
        return state
    question = plan.get("genie_question") or state.get("dr_subject", "")
    result = drafter_tools.query_genie(question, state["genie_room_id"])  # type: ignore[arg-type]
    state["genie_result"] = result
    _append_step(state, "genie", "Queried Genie", json.dumps(result)[:600])
    return state


def _hit_lines(hits: list[dict], prefix: str, start_idx: int) -> tuple[list[str], list[dict]]:
    """Render hits as inline-citable lines + build the citation source list."""
    lines: list[str] = []
    cites: list[dict] = []
    for i, h in enumerate(hits):
        idx = start_idx + i
        title = h.get("document_title") or "Untitled"
        page = h.get("page")
        snippet = (h.get("text") or "").strip().replace("\n", " ")
        lines.append(f"[{idx}] {prefix} — {title} (p.{page}): {snippet[:600]}")
        cites.append(
            {
                "source_type": "kb_chunk",
                "source_id": str(h.get("document_id", "")),
                "label": f"{prefix} :: {title}",
                "snippet": snippet[:500],
                "page": page,
            }
        )
    return lines, cites


@trace(name="draft_node")
def draft_node(state: DrafterState) -> DrafterState:
    case_lines, case_cites = _hit_lines(state.get("case_hits", []), "Case", 1)
    jur_lines, jur_cites = _hit_lines(
        state.get("jurisdiction_hits", []), "Jurisdiction", 1 + len(case_cites)
    )
    pr_lines, pr_cites = _hit_lines(
        state.get("prior_response_hits", []),
        "Prior Response",
        1 + len(case_cites) + len(jur_cites),
    )
    all_cites = case_cites + jur_cites + pr_cites

    memory_block = "\n".join(
        f"- topic={m.get('topic_key')} :: {m.get('fact_text')} (conf={m.get('confidence')})"
        for m in state.get("memory_hits", [])
    ) or "(none)"

    genie_block = ""
    if state.get("genie_result"):
        gr = state["genie_result"] or {}
        if gr.get("rows"):
            genie_block = (
                f"\nGenie SQL: {gr.get('sql')}\nColumns: {gr.get('columns')}\n"
                f"Rows (preview): {json.dumps(gr.get('rows'))[:1500]}\n"
                f"Total rows: {gr.get('row_count')}\n"
            )
            all_cites.append(
                {
                    "source_type": "genie_query",
                    "source_id": gr.get("sql", "")[:200] or "genie",
                    "label": "Genie tabular query",
                    "snippet": json.dumps(gr.get("rows"))[:400],
                    "page": None,
                }
            )

    user_msg = (
        f"DATA REQUEST {state.get('dr_number')} — {state.get('requester')} "
        f"({state.get('requester_kind')})\n"
        f"Subject: {state.get('dr_subject')}\n"
        f"Body: {state.get('dr_body')}\n\n"
        f"=== CASE EVIDENCE ===\n" + "\n".join(case_lines) + "\n\n"
        f"=== JURISDICTION EVIDENCE ===\n" + "\n".join(jur_lines) + "\n\n"
        f"=== PRIOR RESPONSES ===\n" + "\n".join(pr_lines) + "\n\n"
        f"=== POSITION MEMORY (do not contradict) ===\n{memory_block}\n"
        f"{genie_block}\n"
        f"=== USER INSTRUCTION ===\n{state.get('user_instruction') or '(none)'}\n"
        f"=== EXTRA CONTEXT ===\n{state.get('extra_context') or '(none)'}\n\n"
        "Draft the response now."
    )
    resp = chat_completion(
        model=state["model_name"],
        messages=[
            {"role": "system", "content": DRAFT_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.2,
        max_tokens=2500,
    )
    text = resp.choices[0].message.content or ""

    # Try to peel off the trailing CITATIONS_JSON line, if present
    final_text = text
    extracted: list[dict] = []
    if "CITATIONS_JSON:" in text:
        head, _, tail = text.rpartition("CITATIONS_JSON:")
        try:
            extracted = json.loads(tail.strip())
            final_text = head.rstrip()
        except json.JSONDecodeError:
            pass
    citations = extracted or all_cites

    state["draft_text"] = final_text
    state["citations"] = citations
    state["model_version"] = state["model_name"]
    _append_step(state, "llm", "Drafted response", f"{len(final_text)} chars / {len(citations)} citations")
    return state


@trace(name="critique_node")
def critique_node(state: DrafterState) -> DrafterState:
    memory = state.get("memory_hits") or []
    if not memory or not state.get("draft_text"):
        state["position_warnings"] = []
        return state

    payload = {
        "draft": state["draft_text"],
        "memory": [
            {"topic_key": m.get("topic_key"), "fact_text": m.get("fact_text")}
            for m in memory
        ],
    }
    resp = chat_completion(
        model=state["model_name"],
        messages=[
            {"role": "system", "content": CRITIQUE_SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=600,
    )
    try:
        review = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        review = {}
    warnings: list[str] = []
    warnings.extend(review.get("warnings") or [])
    if review.get("missing_citations"):
        warnings.append("Missing citations: " + "; ".join(review["missing_citations"]))
    if review.get("speculation_flags"):
        warnings.append("Speculation flagged: " + "; ".join(review["speculation_flags"]))
    state["position_warnings"] = warnings
    _append_step(state, "tool", "Self-critique", json.dumps(review)[:400])
    return state


@trace(name="finalize_node")
def finalize_node(state: DrafterState) -> DrafterState:
    _append_step(state, "final", "Draft assembled", None)
    return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph():
    if StateGraph is None:
        raise RuntimeError("langgraph is not installed in this environment")
    g = StateGraph(DrafterState)
    g.add_node("plan", plan_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("memory", memory_node)
    g.add_node("genie", genie_node)
    g.add_node("draft", draft_node)
    g.add_node("critique", critique_node)
    g.add_node("finalize", finalize_node)

    g.set_entry_point("plan")
    g.add_edge("plan", "retrieve")
    g.add_edge("retrieve", "memory")
    g.add_edge("memory", "genie")
    g.add_edge("genie", "draft")
    g.add_edge("draft", "critique")
    g.add_edge("critique", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_draft(
    *,
    case_id: str,
    jurisdiction: str,
    dr_number: str,
    dr_subject: str,
    dr_body: str,
    requester: str,
    requester_kind: Optional[str] = None,
    user_instruction: Optional[str] = None,
    extra_context: Optional[str] = None,
    genie_room_id: Optional[str] = None,
    model_name: Optional[str] = None,
) -> dict:
    """Run the drafter graph synchronously and return a dict-shaped ``DraftResult``."""
    settings = get_agent_settings()
    state: DrafterState = {
        "case_id": case_id,
        "jurisdiction": jurisdiction,
        "dr_number": dr_number,
        "dr_subject": dr_subject,
        "dr_body": dr_body,
        "requester": requester,
        "requester_kind": requester_kind,
        "user_instruction": user_instruction,
        "extra_context": extra_context,
        "genie_room_id": genie_room_id,
        "model_name": model_name or settings.drafter_model,
        "steps": [],
    }
    graph = build_graph()
    with agent_run(name=f"draft::{dr_number}") as run_id:
        out: DrafterState = graph.invoke(state)  # type: ignore[assignment]
        out["agent_trace_id"] = run_id

    return {
        "draft_text": out.get("draft_text", ""),
        "citations": out.get("citations", []),
        "steps": out.get("steps", []),
        "agent_trace_id": out.get("agent_trace_id"),
        "model_version": out.get("model_version"),
        "position_warnings": out.get("position_warnings", []),
    }


# ---------------------------------------------------------------------------
# MLflow PyFunc wrapper — what gets registered to UC + deployed to Model Serving
# ---------------------------------------------------------------------------


try:
    import mlflow.pyfunc

    class DrafterAgent(mlflow.pyfunc.PythonModel):
        """Mosaic Model Serving entry point.

        Input dataframe columns must include the keyword args to ``run_draft``.
        """

        def predict(self, context, model_input, params=None):  # type: ignore[override]
            import pandas as pd

            if isinstance(model_input, pd.DataFrame):
                records = model_input.to_dict(orient="records")
            elif isinstance(model_input, dict):
                records = [model_input]
            else:
                records = list(model_input)
            results = [run_draft(**rec) for rec in records]
            return results
except Exception:  # pragma: no cover

    class DrafterAgent:  # type: ignore[no-redef]
        def predict(self, context, model_input, params=None):
            raise RuntimeError("mlflow not available")
