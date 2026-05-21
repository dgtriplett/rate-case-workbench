"""Databricks Job entry point — mines recently-approved Response rows into agent_memory.

Schedule (suggested):
    Every 30 minutes; runs incrementally based on the watermark stored in settings(key="memory_writer.last_run_at").

Logic:
    1. Find Response rows where status in ('approved','filed') and updated_at > watermark.
    2. For each, call the LLM to extract position statements.
    3. Upsert a per-case agent_memory row.
    4. If the parent Case.status = 'closed', additionally write a jurisdiction-scoped copy.
    5. Update watermark.

Idempotency:
    Per-case writes upsert on (case_id, topic_key). Jurisdiction-scoped writes upsert on
    (jurisdiction, topic_key, source_response_id) so re-runs do not duplicate.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from ..common.lakebase import session_scope, shutdown
from ..common.llm import chat_completion
from ..common.mlflow_log import agent_run, setup_mlflow
from ..common.settings import get_agent_settings
from .prompts import SYSTEM

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")
setup_mlflow(experiment_name="/Shared/rcw-memory-writer")


_WATERMARK_KEY = "memory_writer.last_run_at"


async def _get_watermark() -> Optional[datetime]:
    async with session_scope() as sess:
        res = await sess.execute(
            text(
                "SELECT value_json->>'ts' AS ts FROM settings "
                "WHERE key = :k AND scope = 'global'"
            ),
            {"k": _WATERMARK_KEY},
        )
        row = res.first()
        if not row or not row[0]:
            return None
        return datetime.fromisoformat(row[0])


async def _set_watermark(ts: datetime) -> None:
    async with session_scope() as sess:
        await sess.execute(
            text(
                "INSERT INTO settings (key, value_json, scope) "
                "VALUES (:k, CAST(:v AS jsonb), 'global') "
                "ON CONFLICT (key, scope, case_id) DO UPDATE SET "
                "value_json = EXCLUDED.value_json, updated_at = now()"
            ),
            {"k": _WATERMARK_KEY, "v": json.dumps({"ts": ts.isoformat()})},
        )


async def _approved_responses_since(since: Optional[datetime]) -> list[dict]:
    sql = (
        "SELECT r.id::text AS response_id, r.draft_text, r.final_text, r.updated_at, "
        "       r.status::text AS response_status, "
        "       dr.id::text AS data_request_id, dr.subject, dr.body AS dr_body, "
        "       dr.topic_tags, "
        "       c.id::text AS case_id, c.jurisdiction, c.status::text AS case_status, "
        "       c.docket_number "
        "FROM responses r "
        "JOIN data_requests dr ON dr.id = r.data_request_id "
        "JOIN cases c ON c.id = dr.case_id "
        "WHERE r.is_current = TRUE "
        "AND r.status IN ('approved', 'filed') "
    )
    params: dict = {}
    if since is not None:
        sql += "AND r.updated_at > :since "
        params["since"] = since
    sql += "ORDER BY r.updated_at ASC LIMIT 200"
    async with session_scope() as sess:
        res = await sess.execute(text(sql), params)
        return [dict(r) for r in res.mappings().all()]


def extract_positions(
    *,
    case_docket: str,
    dr_subject: str,
    response_text: str,
    topic_tags: list[str],
    model_name: Optional[str] = None,
) -> list[dict]:
    """Use the LLM to extract durable positions from one response."""
    settings = get_agent_settings()
    user = json.dumps(
        {
            "case_docket": case_docket,
            "dr_subject": dr_subject,
            "topic_tags": topic_tags or [],
            "response_text": response_text[:15_000],
        }
    )
    resp = chat_completion(
        model=model_name or settings.memory_writer_model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
        max_tokens=900,
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return []
    positions = parsed.get("positions") or []
    out: list[dict] = []
    for p in positions[:5]:
        topic = (p.get("topic_key") or "").strip()
        fact = (p.get("fact_text") or "").strip()
        if not topic or not fact:
            continue
        conf = float(p.get("confidence") or 0.7)
        conf = max(0.0, min(1.0, conf))
        out.append(
            {
                "topic_key": topic,
                "fact_text": fact,
                "rationale": (p.get("rationale") or "").strip() or None,
                "confidence": conf,
            }
        )
    return out


async def _upsert_case_memory(
    *, case_id: str, response_id: str, position: dict, agent_run_id: Optional[str]
) -> None:
    async with session_scope() as sess:
        # Find existing row for (case_id, topic_key)
        existing = await sess.execute(
            text(
                "SELECT id::text FROM agent_memory "
                "WHERE case_id = CAST(:c AS uuid) AND topic_key = :t AND is_active = TRUE"
            ),
            {"c": case_id, "t": position["topic_key"]},
        )
        old = existing.first()

        new_id = str(uuid.uuid4())
        await sess.execute(
            text(
                "INSERT INTO agent_memory (id, case_id, jurisdiction, topic_key, fact_text, "
                "rationale, source_response_id, confidence, is_active, created_by_agent_run_id) "
                "VALUES (CAST(:id AS uuid), CAST(:c AS uuid), NULL, :t, :f, :r, "
                "CAST(:src AS uuid), :conf, TRUE, :run)"
            ),
            {
                "id": new_id,
                "c": case_id,
                "t": position["topic_key"],
                "f": position["fact_text"],
                "r": position.get("rationale"),
                "src": response_id,
                "conf": position["confidence"],
                "run": agent_run_id,
            },
        )
        if old:
            await sess.execute(
                text(
                    "UPDATE agent_memory SET is_active = FALSE, superseded_by = CAST(:new AS uuid) "
                    "WHERE id = CAST(:old AS uuid)"
                ),
                {"new": new_id, "old": old[0]},
            )


async def _upsert_jurisdiction_memory(
    *,
    jurisdiction: str,
    response_id: str,
    position: dict,
    agent_run_id: Optional[str],
) -> None:
    async with session_scope() as sess:
        existing = await sess.execute(
            text(
                "SELECT id::text FROM agent_memory "
                "WHERE jurisdiction = :j AND topic_key = :t "
                "AND source_response_id = CAST(:r AS uuid)"
            ),
            {"j": jurisdiction, "t": position["topic_key"], "r": response_id},
        )
        if existing.first():
            return  # already wrote a row for this exact source
        await sess.execute(
            text(
                "INSERT INTO agent_memory (case_id, jurisdiction, topic_key, fact_text, "
                "rationale, source_response_id, confidence, is_active, created_by_agent_run_id) "
                "VALUES (NULL, :j, :t, :f, :r, CAST(:src AS uuid), :conf, TRUE, :run)"
            ),
            {
                "j": jurisdiction,
                "t": position["topic_key"],
                "f": position["fact_text"],
                "r": position.get("rationale"),
                "src": response_id,
                "conf": position["confidence"],
                "run": agent_run_id,
            },
        )


async def run_memory_writer(*, since: Optional[datetime] = None) -> dict:
    """Main loop. Returns ``{"processed": N, "positions_written": M}``."""
    if since is None:
        since = await _get_watermark()
    rows = await _approved_responses_since(since)
    log.info("Memory writer: %d candidate response(s)", len(rows))

    processed = 0
    positions_written = 0
    latest_ts: Optional[datetime] = since

    with agent_run(name="memory_writer.batch") as run_id:
        for r in rows:
            text_blob = r.get("final_text") or r.get("draft_text") or ""
            if not text_blob.strip():
                continue
            positions = extract_positions(
                case_docket=r.get("docket_number", ""),
                dr_subject=r.get("subject", ""),
                response_text=text_blob,
                topic_tags=r.get("topic_tags") or [],
            )
            for p in positions:
                await _upsert_case_memory(
                    case_id=r["case_id"],
                    response_id=r["response_id"],
                    position=p,
                    agent_run_id=run_id,
                )
                positions_written += 1
                if r.get("case_status") == "closed" and r.get("jurisdiction"):
                    await _upsert_jurisdiction_memory(
                        jurisdiction=r["jurisdiction"],
                        response_id=r["response_id"],
                        position=p,
                        agent_run_id=run_id,
                    )
                    positions_written += 1
            processed += 1
            ts = r.get("updated_at")
            if ts and (latest_ts is None or ts > latest_ts):
                latest_ts = ts

    if latest_ts is not None:
        await _set_watermark(latest_ts)

    return {"processed": processed, "positions_written": positions_written}


def main() -> int:
    parser = argparse.ArgumentParser(description="Mine approved responses into agent_memory")
    parser.add_argument("--since", help="ISO timestamp; overrides stored watermark")
    args = parser.parse_args()
    since = datetime.fromisoformat(args.since) if args.since else None

    try:
        result = asyncio.run(run_memory_writer(since=since))
    finally:
        try:
            asyncio.run(shutdown())
        except Exception:
            pass
    log.info("Memory writer result: %s", result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
