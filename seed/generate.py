"""LLM-author the synthetic NLPG rate-case document corpus.

Writes:
    - Documents to ``<docs_volume>/<docket>/<kind>/<slug>.txt``
    - A manifest JSON to ``seed/output/manifest.json`` (so ``seed_db.py`` can ingest)

The script is idempotent: it skips any document whose target file already exists
unless ``--force`` is supplied.

Usage::

    DATABRICKS_PROFILE=fe-vm-grid-ops-demo python -m seed.generate
    DATABRICKS_PROFILE=fe-vm-grid-ops-demo python -m seed.generate --force --only application
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from databricks.sdk import WorkspaceClient
from openai import OpenAI

# Allow ``python -m seed.generate`` regardless of cwd
import os
try:
    _SCRIPT_ROOT = Path(__file__).resolve().parent.parent
except NameError:
    _SCRIPT_ROOT = Path(os.environ.get("RCW_PROJECT_ROOT", "/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench"))
ROOT = _SCRIPT_ROOT
sys.path.insert(0, str(ROOT))

from seed.prompts import (  # noqa: E402
    application,
    data_requests,
    orders,
    policies,
    prior_responses,
    testimony,
)

log = logging.getLogger("generate")
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


# ---------------------------------------------------------------------------
# Workspace + LLM client (Databricks Foundation Model API via OpenAI SDK)
# ---------------------------------------------------------------------------


def _workspace() -> WorkspaceClient:
    profile = os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
    if os.environ.get("DATABRICKS_HOST") and os.environ.get("DATABRICKS_TOKEN"):
        return WorkspaceClient()
    return WorkspaceClient(profile=profile)


def _openai_client() -> tuple[OpenAI, WorkspaceClient]:
    wc = _workspace()
    host = wc.config.host
    if host and not host.startswith("http"):
        host = f"https://{host}"
    headers = wc.config.authenticate()
    auth = headers.get("Authorization", "")
    token = auth[len("Bearer "):] if auth.startswith("Bearer ") else (wc.config.token or "")
    if not host or not token:
        raise RuntimeError("Could not resolve host/token from Databricks profile")
    return OpenAI(api_key=token, base_url=f"{host.rstrip('/')}/serving-endpoints"), wc


GENERATOR_MODEL = os.environ.get("GENERATOR_MODEL", "databricks-claude-sonnet-4-6")


def _chat(client: OpenAI, messages: list[dict], *, json_mode: bool = False, max_tokens: int = 4000) -> str:
    kwargs: dict[str, Any] = {
        "model": GENERATOR_MODEL,
        "messages": messages,
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }
    # Claude endpoints on Databricks don't support response_format=json_object.
    # When json_mode is requested, we ask the model to emit JSON (prompt-only)
    # and extract the first balanced object/array from the response.
    if json_mode:
        msgs = list(messages)
        if msgs and msgs[0].get("role") == "system":
            msgs[0] = {
                "role": "system",
                "content": msgs[0]["content"] + "\n\nReturn ONLY a valid JSON object — no prose, no markdown fences.",
            }
        else:
            msgs.insert(0, {"role": "system", "content": "Return ONLY a valid JSON object — no prose, no markdown fences."})
        kwargs["messages"] = msgs

    for attempt in range(3):
        try:
            r = client.chat.completions.create(**kwargs)
            content = r.choices[0].message.content or ""
            if json_mode:
                return _extract_json_blob(content)
            return content
        except Exception as e:
            log.warning("LLM call failed (attempt %d): %s", attempt + 1, e)
            time.sleep(2 ** attempt)
    raise RuntimeError("LLM call failed after retries")


def _extract_json_blob(text: str) -> str:
    """Return the first balanced {...} or [...] substring from text."""
    text = text.strip()
    if text.startswith("```"):
        # strip markdown code fences
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    # find first { or [
    for i, ch in enumerate(text):
        if ch in "{[":
            opener, closer = ch, "}" if ch == "{" else "]"
            depth = 0
            in_str = False
            esc = False
            for j in range(i, len(text)):
                c = text[j]
                if in_str:
                    if esc:
                        esc = False
                    elif c == "\\":
                        esc = True
                    elif c == '"':
                        in_str = False
                else:
                    if c == '"':
                        in_str = True
                    elif c == opener:
                        depth += 1
                    elif c == closer:
                        depth -= 1
                        if depth == 0:
                            return text[i : j + 1]
            break
    return text  # fall through; caller will surface JSONDecodeError


# ---------------------------------------------------------------------------
# Volume IO — write to UC Volume in workspace, mirror locally under seed/output
# ---------------------------------------------------------------------------


def _slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:80]


def _ensure_volume(wc: WorkspaceClient, volume_path: str) -> None:
    try:
        wc.files.create_directory(volume_path)
    except Exception:
        pass  # exists or not supported on older SDKs


def _upload(wc: WorkspaceClient, volume_path: str, body: str) -> None:
    import io as _io
    parent = volume_path.rsplit("/", 1)[0]
    _ensure_volume(wc, parent)
    data = body.encode("utf-8")
    # SDK requires a file-like object that exposes seekable(); wrap bytes in BytesIO.
    stream = _io.BytesIO(data)
    try:
        wc.files.upload(file_path=volume_path, contents=stream, overwrite=True)
    except TypeError:
        stream.seek(0)
        wc.files.upload(volume_path, stream, overwrite=True)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


OUTPUT_DIR = ROOT / "seed" / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"


def _load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return {
        "generated_at": None,
        "cases": [],
        "documents": [],
        "data_requests": [],
        "prior_responses": [],
    }


def _save_manifest(manifest: dict) -> None:
    manifest["generated_at"] = datetime.utcnow().isoformat()
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, default=str))


def _local_mirror_path(volume_path: str, docs_volume: str) -> Path:
    rel = volume_path[len(docs_volume) :].lstrip("/")
    p = OUTPUT_DIR / "docs_raw" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------


def _build_cases(facts: dict) -> list[dict]:
    jur = "State of Cascadia"
    commission = facts["regulator"]["name"]
    util = facts["utility"]["legal_name"]
    cases = [
        {
            "id": str(uuid.uuid4()),
            "name": "NLPG 2026 General Rate Case",
            "docket_number": "NLPG-26-001",
            "jurisdiction": jur,
            "commission": commission,
            "utility_name": util,
            "case_type": "general_rate_case",
            "description": "Application for authority to increase rates and charges; combined electric + gas.",
            "filed_date": "2026-01-21",
            "target_decision_date": "2027-01-20",
            "status": "active",
        },
        {
            "id": str(uuid.uuid4()),
            "name": "NLPG 2022 General Rate Case",
            "docket_number": "NLPG-22-005",
            "jurisdiction": jur,
            "commission": commission,
            "utility_name": util,
            "case_type": "general_rate_case",
            "description": "Closed 2022 general rate case; settled at 9.55% ROE.",
            "filed_date": "2022-06-15",
            "target_decision_date": "2023-06-15",
            "status": "closed",
        },
        {
            "id": str(uuid.uuid4()),
            "name": "NLPG 2024 ROE-Only Proceeding",
            "docket_number": "NLPG-24-003",
            "jurisdiction": jur,
            "commission": commission,
            "utility_name": util,
            "case_type": "roe_only",
            "description": "Closed 2024 ROE-only proceeding; ROE confirmed at 9.55%.",
            "filed_date": "2024-02-10",
            "target_decision_date": "2024-10-30",
            "status": "closed",
        },
    ]
    return cases


# ---------------------------------------------------------------------------
# Document writers
# ---------------------------------------------------------------------------


def _doc_entry(*, docket: str, title: str, kind: str, classification: str, content: str,
               docs_volume: str, witnesses: Optional[list[str]] = None) -> dict:
    slug = _slugify(title)
    rel = f"{docket}/{kind}/{slug}.txt"
    volume_path = f"{docs_volume.rstrip('/')}/{rel}"
    return {
        "id": str(uuid.uuid4()),
        "docket": docket,
        "title": title,
        "kind": kind,
        "classification": classification,
        "volume_path": volume_path,
        "content": content,
        "witnesses": witnesses or [],
        "page_count": max(1, len(content) // 2500),
    }


def generate_application_set(client: OpenAI, facts: dict, docket: str, docs_volume: str) -> list[dict]:
    docs: list[dict] = []
    log.info("[%s] application", docket)
    body = _chat(client, application.application_messages(facts, docket), max_tokens=4500)
    docs.append(_doc_entry(
        docket=docket, title=f"Application of {facts['utility']['legal_name']} ({docket})",
        kind="filing", classification="public", content=body, docs_volume=docs_volume,
    ))
    for key in application.EXHIBIT_KEYS:
        log.info("[%s] exhibit %s", docket, key)
        body = _chat(client, application.exhibit_messages(facts, key), max_tokens=3500)
        docs.append(_doc_entry(
            docket=docket, title=f"Exhibit — {key.replace('_', ' ').title()}",
            kind="exhibit", classification="public", content=body, docs_volume=docs_volume,
        ))
    return docs


def generate_testimony_set(client: OpenAI, facts: dict, docket: str, docs_volume: str) -> list[dict]:
    docs: list[dict] = []
    for w in facts["witnesses"]:
        log.info("[%s] testimony %s (%s)", docket, w["name"], w["id"])
        body = _chat(client, testimony.testimony_messages(facts, w, docket), max_tokens=3500)
        docs.append(_doc_entry(
            docket=docket,
            title=f"Direct Testimony of {w['name']}",
            kind="testimony",
            classification="public",
            content=body,
            docs_volume=docs_volume,
            witnesses=[w["name"]],
        ))
    return docs


def generate_orders(client: OpenAI, facts: dict, docs_volume: str) -> list[dict]:
    docs: list[dict] = []
    for po in facts["prior_orders"]:
        log.info("[%s] order %s", po["docket"], po["order_no"])
        body = _chat(client, orders.order_messages(facts, po), max_tokens=4500)
        docs.append(_doc_entry(
            docket=po["docket"],
            title=f"{po['order_no']} — {po['title']}",
            kind="order",
            classification="public",
            content=body,
            docs_volume=docs_volume,
        ))
    return docs


def generate_policies(client: OpenAI, facts: dict, active_docket: str, docs_volume: str) -> list[dict]:
    docs: list[dict] = []
    for doc_id, title in policies.POLICY_TOPICS:
        log.info("[policy] %s", doc_id)
        body = _chat(client, policies.policy_messages(facts, doc_id, title), max_tokens=2500)
        docs.append(_doc_entry(
            docket=active_docket,
            title=f"{doc_id} — {title}",
            kind="policy",
            classification="confidential",
            content=body,
            docs_volume=docs_volume,
        ))
    return docs


# ---------------------------------------------------------------------------
# Data requests + prior responses
# ---------------------------------------------------------------------------


def generate_data_requests(
    client: OpenAI, facts: dict, docket: str, target_count: int = 60
) -> list[dict]:
    out: list[dict] = []
    counters: dict[str, int] = {
        "CPUC-X Staff": 0,
        "Office of Consumer Advocacy": 0,
        "Cascadia Industrial Energy Users": 0,
        "Cascadia Climate Action": 0,
    }
    batch_size = 5
    consecutive_bad = 0
    while len(out) < target_count:
        if consecutive_bad >= 5:
            log.warning("DR generator stuck after %d bad batches; stopping early with %d/%d", consecutive_bad, len(out), target_count)
            break
        prefer_echoes = len(out) >= target_count - 18  # last 18 lean on echoes (≥6 echoing prior case)
        log.info("[%s] DR batch (have %d/%d, echoes=%s)", docket, len(out), target_count, prefer_echoes)
        raw = _chat(
            client,
            data_requests.batch_messages(facts, docket, batch_size, counters, prefer_echoes),
            json_mode=True,
            max_tokens=6000,
        )
        try:
            parsed = json.loads(raw)
            consecutive_bad = 0
        except json.JSONDecodeError as e:
            log.warning("DR batch JSON malformed (%s): first 200 chars: %s", e, raw[:200].replace("\n"," "))
            consecutive_bad += 1
            continue
        for req in parsed.get("requests", []):
            requester = req.get("requester", "CPUC-X Staff")
            counters[requester] = counters.get(requester, 0) + 1
            # Synthesize issued/due dates spread over the discovery phase
            base = date(2026, 3, 1)
            issued = base + timedelta(days=(len(out) * 2) % 90)
            due = issued + timedelta(days=21)
            out.append({
                "id": str(uuid.uuid4()),
                "docket": docket,
                "dr_number": req.get("dr_number") or f"DR-{len(out)+1:03d}",
                "requester": requester,
                "requester_kind": req.get("requester_kind", "other"),
                "subject": req.get("subject", "")[:512],
                "body": req.get("body", ""),
                "topic_tags": req.get("topic_tags", []),
                "priority": req.get("priority", "normal"),
                "issued_date": issued.isoformat(),
                "due_date": due.isoformat(),
                "echoes_prior_case": req.get("echoes_prior_case"),
                "status": "new",
            })
            if len(out) >= target_count:
                break
    return out[:target_count]


def generate_prior_responses_for_case(
    client: OpenAI, facts: dict, prior_case: dict, target_count: int
) -> tuple[list[dict], list[dict]]:
    """Return (synthetic_requests, responses) for one closed case."""
    # First synthesize a small DR set for the closed case so we can answer them.
    log.info("[%s] synthesizing %d historical DRs", prior_case["docket"], target_count)
    drs: list[dict] = []
    counters = {
        "CPUC-X Staff": 0,
        "Office of Consumer Advocacy": 0,
        "Cascadia Industrial Energy Users": 0,
        "Cascadia Climate Action": 0,
    }
    bad = 0
    while len(drs) < target_count:
        if bad >= 5:
            log.warning("prior-DR gen stuck after %d bad batches; stopping with %d/%d", bad, len(drs), target_count)
            break
        batch = min(5, target_count - len(drs))
        raw = _chat(
            client,
            data_requests.batch_messages(facts, prior_case["docket"], batch, counters, False),
            json_mode=True,
            max_tokens=5500,
        )
        try:
            parsed = json.loads(raw)
            bad = 0
        except json.JSONDecodeError as e:
            log.warning("prior-DR JSON malformed (%s): %s", e, raw[:200].replace("\n", " "))
            bad += 1
            continue
        for req in parsed.get("requests", []):
            requester = req.get("requester", "CPUC-X Staff")
            counters[requester] = counters.get(requester, 0) + 1
            issue_year = int(prior_case["docket"].split("-")[1]) + 2000
            base = date(issue_year, 8, 1)
            issued = base + timedelta(days=(len(drs) * 3) % 120)
            due = issued + timedelta(days=21)
            drs.append({
                "id": str(uuid.uuid4()),
                "docket": prior_case["docket"],
                "dr_number": req.get("dr_number") or f"DR-{len(drs)+1:03d}",
                "requester": requester,
                "requester_kind": req.get("requester_kind", "other"),
                "subject": req.get("subject", "")[:512],
                "body": req.get("body", ""),
                "topic_tags": req.get("topic_tags", []),
                "priority": req.get("priority", "normal"),
                "issued_date": issued.isoformat(),
                "due_date": due.isoformat(),
                "status": "filed",
            })
            if len(drs) >= target_count:
                break

    # Now ask the LLM to draft filed responses for those DRs.
    responses: list[dict] = []
    batch = 3
    for i in range(0, len(drs), batch):
        chunk = drs[i : i + batch]
        log.info("[%s] response batch %d-%d", prior_case["docket"], i, i + len(chunk))
        compact = [
            {
                "dr_number": d["dr_number"],
                "requester": d["requester"],
                "subject": d["subject"],
                "body": d["body"],
                "topic_tags": d["topic_tags"],
                "issued_date": d["issued_date"],
            }
            for d in chunk
        ]
        raw = _chat(
            client,
            prior_responses.batch_messages(facts, prior_case, compact),
            json_mode=True,
            max_tokens=6000,
        )
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            log.warning("prior-response JSON malformed (%s): %s", e, raw[:200].replace("\n", " "))
            continue
        by_num = {d["dr_number"]: d for d in chunk}
        for r in parsed.get("responses", []):
            dr_num = r.get("dr_number")
            dr = by_num.get(dr_num)
            if not dr:
                continue
            responses.append({
                "id": str(uuid.uuid4()),
                "data_request_id": dr["id"],
                "docket": prior_case["docket"],
                "dr_number": dr_num,
                "filed_date": r.get("filed_date") or dr["due_date"],
                "response_text": r.get("response_text", ""),
                "prepared_by_witness_id": r.get("prepared_by_witness_id"),
                "position_topic_tags": r.get("position_topic_tags", []),
                "status": "filed",
            })
    return drs, responses


# ---------------------------------------------------------------------------
# Top-level driver
# ---------------------------------------------------------------------------


def write_doc(wc: WorkspaceClient, doc: dict, docs_volume: str, force: bool) -> None:
    local = _local_mirror_path(doc["volume_path"], docs_volume)
    local.parent.mkdir(parents=True, exist_ok=True)
    if not local.exists() or force:
        local.write_text(doc["content"])
    # Always (idempotently) upload to UC Volume — earlier runs may have failed mid-upload
    try:
        _upload(wc, doc["volume_path"], doc["content"])
    except Exception as e:
        log.warning("UC volume upload failed (%s) — local copy kept", e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["application", "testimony", "orders", "policies",
                                            "data_requests", "prior_responses", "all"],
                        default="all")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--docs-volume",
                        default=os.environ.get("DOCS_VOLUME",
                                               "/Volumes/grid_ops_demo_catalog/rcw_knowledge/docs_raw"))
    args = parser.parse_args()

    facts = json.loads((ROOT / "seed" / "nlpg_facts.json").read_text())
    client, wc = _openai_client()
    manifest = _load_manifest()

    if not manifest["cases"]:
        manifest["cases"] = _build_cases(facts)
        _save_manifest(manifest)
    cases_by_docket = {c["docket_number"]: c for c in manifest["cases"]}

    active_docket = "NLPG-26-001"

    all_docs: list[dict] = manifest.get("documents", [])
    by_title = {(d["docket"], d["title"]) for d in all_docs}

    def _add_docs(new_docs: list[dict]) -> None:
        added = 0
        for d in new_docs:
            if (d["docket"], d["title"]) in by_title and not args.force:
                continue
            write_doc(wc, d, args.docs_volume, args.force)
            all_docs.append(d)
            by_title.add((d["docket"], d["title"]))
            added += 1
        if added:
            manifest["documents"] = all_docs
            _save_manifest(manifest)

    if args.only in {"application", "all"}:
        _add_docs(generate_application_set(client, facts, active_docket, args.docs_volume))

    if args.only in {"testimony", "all"}:
        _add_docs(generate_testimony_set(client, facts, active_docket, args.docs_volume))

    if args.only in {"orders", "all"}:
        _add_docs(generate_orders(client, facts, args.docs_volume))

    if args.only in {"policies", "all"}:
        _add_docs(generate_policies(client, facts, active_docket, args.docs_volume))

    if args.only in {"data_requests", "all"}:
        existing_drs = {(d["docket"], d["dr_number"]) for d in manifest.get("data_requests", [])}
        if not any(d for d in manifest.get("data_requests", []) if d["docket"] == active_docket):
            drs = generate_data_requests(client, facts, active_docket, target_count=60)
            manifest.setdefault("data_requests", []).extend(drs)
            _save_manifest(manifest)

    if args.only in {"prior_responses", "all"}:
        prior_orders_by_docket = {po["docket"]: po for po in facts["prior_orders"]}
        for closed_docket, target in [("NLPG-22-005", 25), ("NLPG-24-003", 15)]:
            already = [r for r in manifest.get("prior_responses", []) if r["docket"] == closed_docket]
            if already and not args.force:
                continue
            prior_case = prior_orders_by_docket.get(closed_docket, {"docket": closed_docket})
            drs, responses = generate_prior_responses_for_case(client, facts, prior_case, target)
            manifest.setdefault("data_requests", []).extend(drs)
            manifest.setdefault("prior_responses", []).extend(responses)
            _save_manifest(manifest)

    _save_manifest(manifest)
    log.info(
        "Done. cases=%d documents=%d data_requests=%d prior_responses=%d",
        len(manifest["cases"]),
        len(manifest.get("documents", [])),
        len(manifest.get("data_requests", [])),
        len(manifest.get("prior_responses", [])),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
