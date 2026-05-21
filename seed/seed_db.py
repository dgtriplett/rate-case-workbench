"""Populate Lakebase + Delta with the synthetic NLPG corpus.

Order of operations:
    1. Read ``seed/output/manifest.json`` (produced by ``seed/generate.py``).
    2. Upsert cases, case_phases, witnesses, documents, data_requests, responses,
       knowledge_chunks placeholders into Lakebase Postgres.
    3. Create the Delta tables in ``grid_ops_demo_catalog.rcw_tabular`` and load
       mathematically-consistent rows for 2020-2026 using the Databricks SQL
       Statement Execution API.

Idempotent: re-running upserts on natural keys (docket_number, dr_number, title).

Usage::

    DATABRICKS_PROFILE=fe-vm-grid-ops-demo \
    PGHOST=… PGUSER=… python -m seed.seed_db
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import date, datetime


def _parse_date(value):
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _parse_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    return None
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

import os
try:
    _SCRIPT_ROOT = Path(__file__).resolve().parent.parent
except NameError:
    _SCRIPT_ROOT = Path(os.environ.get("RCW_PROJECT_ROOT", "/Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench"))
ROOT = _SCRIPT_ROOT
sys.path.insert(0, str(ROOT))

from backend.databricks_client import get_lakebase_token, get_oauth_token, get_workspace_host  # noqa: E402

log = logging.getLogger("seed_db")
logging.basicConfig(level=logging.INFO, format="%(levelname)s :: %(message)s")


CATALOG = os.environ.get("UC_CATALOG", "grid_ops_demo_catalog")
TABULAR_SCHEMA = os.environ.get("UC_TABULAR_SCHEMA", "rcw_tabular")
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "7fb5ec85684023e6")


MANIFEST_PATH = ROOT / "seed" / "output" / "manifest.json"


# ---------------------------------------------------------------------------
# Lakebase connection
# ---------------------------------------------------------------------------


def _build_url() -> str:
    host = os.environ.get("PGHOST")
    port = os.environ.get("PGPORT", "5432")
    db = os.environ.get("PGDATABASE", "databricks_postgres")
    user = os.environ.get("PGUSER")
    if not host or not user:
        from databricks.sdk import WorkspaceClient
        try:
            w = WorkspaceClient() if os.environ.get("DATABRICKS_HOST") else WorkspaceClient(
                profile=os.environ.get("DATABRICKS_PROFILE", "fe-vm-grid-ops-demo")
            )
        except Exception:
            w = WorkspaceClient()
        instance = w.database.get_database_instance(
            name=os.environ.get("LAKEBASE_INSTANCE", "rcw-lakebase")
        )
        host = host or instance.read_write_dns
        user = user or (w.current_user.me().user_name or "")
        log.info("auto-discovered Lakebase host=%s user=%s", host, user)
    token = get_lakebase_token(os.environ.get("LAKEBASE_INSTANCE", "rcw-lakebase"))
    return f"postgresql+asyncpg://{quote_plus(user)}:{quote_plus(token)}@{host}:{port}/{db}"


# ---------------------------------------------------------------------------
# Lakebase upserts
# ---------------------------------------------------------------------------


PHASE_TEMPLATE: list[tuple[str, int]] = [
    ("pre_filing", 1),
    ("filing", 2),
    ("discovery", 3),
    ("direct_testimony", 4),
    ("rebuttal", 5),
    ("surrebuttal", 6),
    ("hearing", 7),
    ("post_hearing_briefs", 8),
    ("order", 9),
    ("compliance", 10),
]


async def _upsert_cases(engine, cases: list[dict]) -> dict[str, str]:
    """Return docket → case_id mapping. Idempotent on docket_number."""
    mapping: dict[str, str] = {}
    async with engine.begin() as conn:
        for c in cases:
            res = await conn.execute(
                text(
                    "INSERT INTO cases (id, name, docket_number, jurisdiction, commission, "
                    "utility_name, case_type, description, filed_date, target_decision_date, status) "
                    "VALUES (CAST(:id AS uuid), :name, :docket, :jur, :comm, :util, :ct, :desc, "
                    "CAST(:fd AS DATE), CAST(:td AS DATE), CAST(:status AS case_status)) "
                    "ON CONFLICT (docket_number) DO UPDATE SET "
                    "  name = EXCLUDED.name, description = EXCLUDED.description, "
                    "  status = EXCLUDED.status, updated_at = now() "
                    "RETURNING id::text"
                ),
                {
                    "id": c["id"],
                    "name": c["name"],
                    "docket": c["docket_number"],
                    "jur": c["jurisdiction"],
                    "comm": c["commission"],
                    "util": c["utility_name"],
                    "ct": c["case_type"],
                    "desc": c.get("description"),
                    "fd": _parse_date(c.get("filed_date")),
                    "td": _parse_date(c.get("target_decision_date")),
                    "status": c["status"],
                },
            )
            row = res.first()
            mapping[c["docket_number"]] = row[0]
    return mapping


async def _seed_phases(engine, case_ids: dict[str, str]) -> None:
    async with engine.begin() as conn:
        for docket, case_id in case_ids.items():
            for ptype, seq in PHASE_TEMPLATE:
                await conn.execute(
                    text(
                        "INSERT INTO case_phases (case_id, phase_type, sequence, status) "
                        "VALUES (CAST(:c AS uuid), CAST(:p AS phase_type), :s, "
                        "        CAST(:st AS phase_status)) "
                        "ON CONFLICT (case_id, phase_type) DO NOTHING"
                    ),
                    {"c": case_id, "p": ptype, "s": seq,
                     "st": "in_progress" if (docket == "NLPG-26-001" and ptype == "discovery") else "not_started"},
                )


async def _seed_witnesses(engine, witnesses: list[dict]) -> dict[str, str]:
    """Return witness_external_id → witness uuid (str)."""
    mapping: dict[str, str] = {}
    async with engine.begin() as conn:
        for w in witnesses:
            res = await conn.execute(
                text(
                    "SELECT id::text FROM witnesses WHERE name = :n LIMIT 1"
                ),
                {"n": w["name"]},
            )
            row = res.first()
            if row:
                mapping[w["id"]] = row[0]
                continue
            new_id = str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO witnesses (id, name, title, expertise_areas, is_external) "
                    "VALUES (CAST(:id AS uuid), :n, :t, :e, :ex)"
                ),
                {
                    "id": new_id,
                    "n": w["name"],
                    "t": w.get("title"),
                    "e": w.get("expertise", []),
                    "ex": bool(w.get("external", False)),
                },
            )
            mapping[w["id"]] = new_id
    return mapping


async def _seed_documents(engine, docs: list[dict], case_ids: dict[str, str]) -> dict[str, str]:
    """Return manifest doc id → db doc id mapping."""
    mapping: dict[str, str] = {}
    async with engine.begin() as conn:
        for d in docs:
            case_id = case_ids.get(d["docket"])
            page_count = d.get("page_count")
            existing = await conn.execute(
                text("SELECT id::text FROM documents WHERE uri = :u"),
                {"u": d["volume_path"]},
            )
            row = existing.first()
            if row:
                mapping[d["id"]] = row[0]
                continue
            new_id = d.get("id") or str(uuid.uuid4())
            await conn.execute(
                text(
                    "INSERT INTO documents (id, case_id, title, kind, uri, page_count, classification, topic_tags) "
                    "VALUES (CAST(:id AS uuid), CAST(:cid AS uuid), "
                    "        :title, CAST(:kind AS document_kind), :uri, :pc, "
                    "        CAST(:cls AS classification), CAST(:tags AS TEXT[]))"
                ),
                {
                    "id": new_id,
                    "cid": case_id,
                    "title": d["title"],
                    "kind": d["kind"],
                    "uri": d["volume_path"],
                    "pc": page_count,
                    "cls": d.get("classification", "public"),
                    "tags": d.get("topic_tags", []),
                },
            )
            mapping[d["id"]] = new_id
    return mapping


async def _seed_data_requests(engine, drs: list[dict], case_ids: dict[str, str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    async with engine.begin() as conn:
        for d in drs:
            case_id = case_ids.get(d["docket"])
            if not case_id:
                continue
            res = await conn.execute(
                text(
                    "INSERT INTO data_requests (id, case_id, dr_number, requester, requester_kind, "
                    "issued_date, due_date, subject, body, status, priority, topic_tags) "
                    "VALUES (CAST(:id AS uuid), CAST(:c AS uuid), :n, :r, :rk, "
                    "        CAST(:i AS DATE), CAST(:du AS DATE), :s, :b, "
                    "        CAST(:st AS dr_status), :p, :tags) "
                    "ON CONFLICT (case_id, dr_number) DO UPDATE SET "
                    "  subject = EXCLUDED.subject, body = EXCLUDED.body, "
                    "  topic_tags = EXCLUDED.topic_tags, updated_at = now() "
                    "RETURNING id::text"
                ),
                {
                    "id": d["id"],
                    "c": case_id,
                    "n": d["dr_number"],
                    "r": d["requester"],
                    "rk": d.get("requester_kind"),
                    "i": _parse_date(d["issued_date"]),
                    "du": _parse_date(d["due_date"]),
                    "s": d["subject"][:512],
                    "b": d["body"],
                    "st": d.get("status", "new"),
                    "p": d.get("priority", "normal"),
                    "tags": d.get("topic_tags", []),
                },
            )
            row = res.first()
            if row:
                mapping[d["id"]] = row[0]
    return mapping


async def _seed_responses(engine, responses: list[dict], dr_ids: dict[str, str]) -> None:
    async with engine.begin() as conn:
        for r in responses:
            data_request_id = dr_ids.get(r["data_request_id"])
            if not data_request_id:
                continue
            await conn.execute(
                text(
                    "INSERT INTO responses (id, data_request_id, version, is_current, draft_text, "
                    "final_text, status, filed_at) "
                    "VALUES (CAST(:id AS uuid), CAST(:drid AS uuid), 1, TRUE, NULL, :ft, "
                    "        CAST(:st AS response_status), CAST(:filed_at AS TIMESTAMPTZ)) "
                    "ON CONFLICT (data_request_id, version) DO UPDATE SET "
                    "  final_text = EXCLUDED.final_text, status = EXCLUDED.status, "
                    "  filed_at = EXCLUDED.filed_at, updated_at = now()"
                ),
                {
                    "id": r["id"],
                    "drid": data_request_id,
                    "ft": r["response_text"],
                    "st": r.get("status", "filed"),
                    "filed_at": _parse_datetime(r.get("filed_date")),
                },
            )


async def _seed_knowledge_chunks_placeholders(engine, doc_ids: dict[str, str]) -> None:
    """Insert one placeholder chunk per document.

    The real chunking + indexing is done by the ingest pipeline (Vector Search) — this
    placeholder ensures the Lakebase knowledge_chunks table is non-empty for demos and
    that downstream FK joins work before VS is built.
    """
    async with engine.begin() as conn:
        for db_id in doc_ids.values():
            await conn.execute(
                text(
                    "INSERT INTO knowledge_chunks (document_id, chunk_index, text_preview, "
                    "page, char_start, char_end) "
                    "VALUES (CAST(:d AS uuid), 0, :p, 1, 0, 1000) "
                    "ON CONFLICT DO NOTHING"
                ),
                {"d": db_id, "p": "(placeholder — see UC Volume for full text)"},
            )


async def _seed_genie_room_placeholder(engine) -> None:
    """Insert/update the Genie room row.

    Resolves the space id from (in order):
      1. ``GENIE_SPACE_ID`` env var
      2. ``seed/output/genie_space_id.txt`` written by ``setup_genie_space.py``
    """
    rid = os.environ.get("GENIE_SPACE_ID")
    if not rid:
        try:
            p = ROOT / "seed" / "output" / "genie_space_id.txt"
            if p.exists():
                rid = p.read_text().strip()
        except Exception:
            pass
    if not rid:
        return
    log.info("Registering Genie space %s in genie_rooms", rid)
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO genie_rooms (room_id, label, description, allowed_roles) "
                "VALUES (:r, 'rcw-evidence-genie', 'Tabular evidence over rate base, O&M, capex, etc.', "
                "        ARRAY['case_manager','witness','reviewer','approver','admin']) "
                "ON CONFLICT (room_id) DO NOTHING"
            ),
            {"r": rid},
        )


# ---------------------------------------------------------------------------
# Delta tables via SQL Statement Execution API
# ---------------------------------------------------------------------------


def _sql_exec(sql: str, *, timeout_sec: int = 120) -> dict:
    """Execute one or more SQL statements; the Databricks SQL Statements API
    only supports one statement per call, so we split on top-level semicolons."""
    host = get_workspace_host().rstrip("/")
    token = get_oauth_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    last_body: dict = {}
    with httpx.Client(timeout=timeout_sec + 10) as client:
        for stmt in statements:
            payload = {
                "statement": stmt,
                "warehouse_id": WAREHOUSE_ID,
                "wait_timeout": f"{min(timeout_sec, 50)}s",
                "on_wait_timeout": "CONTINUE",
            }
            r = client.post(f"{host}/api/2.0/sql/statements/", headers=headers, json=payload)
            r.raise_for_status()
            body = r.json()
            statement_id = body.get("statement_id")
            state = (body.get("status") or {}).get("state")
            deadline = time.time() + timeout_sec
            while state in {"PENDING", "RUNNING"} and time.time() < deadline:
                time.sleep(2)
                r2 = client.get(f"{host}/api/2.0/sql/statements/{statement_id}", headers=headers)
                r2.raise_for_status()
                body = r2.json()
                state = (body.get("status") or {}).get("state")
            if state != "SUCCEEDED":
                raise RuntimeError(f"SQL failed: {state} — {body}")
            last_body = body
    return last_body


def _ensure_tabular_schema() -> None:
    log.info("Ensuring %s.%s schema exists", CATALOG, TABULAR_SCHEMA)
    _sql_exec(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{TABULAR_SCHEMA}`")


def _t(name: str) -> str:
    return f"`{CATALOG}`.`{TABULAR_SCHEMA}`.`{name}`"


def _create_delta_tables() -> None:
    statements = [
        f"""CREATE TABLE IF NOT EXISTS {_t('rate_base')} (
              year INT,
              function STRING,
              plant_in_service DOUBLE,
              accumulated_depr DOUBLE,
              net_rate_base DOUBLE
            ) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {_t('om_expenses')} (
              year INT,
              function STRING,
              account STRING,
              amount DOUBLE
            ) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {_t('capex_plan')} (
              year INT,
              project STRING,
              function STRING,
              amount DOUBLE,
              status STRING
            ) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {_t('customer_counts')} (
              year INT,
              class STRING,
              customers BIGINT,
              sales_mwh DOUBLE
            ) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {_t('billing_determinants')} (
              year INT,
              class STRING,
              sales DOUBLE,
              revenue DOUBLE,
              average_rate DOUBLE
            ) USING DELTA""",
        f"""CREATE TABLE IF NOT EXISTS {_t('roe_history')} (
              year INT,
              jurisdiction STRING,
              authorized_roe DOUBLE,
              capital_structure_equity_pct DOUBLE
            ) USING DELTA""",
    ]
    for s in statements:
        _sql_exec(s)


def _row_values(rows: list[tuple]) -> str:
    """Render Python tuples as Spark SQL VALUES clauses."""
    def render(v):
        if v is None:
            return "NULL"
        if isinstance(v, str):
            esc = v.replace("'", "''")
            return f"'{esc}'"
        return str(v)
    return ",\n".join("(" + ", ".join(render(v) for v in row) + ")" for row in rows)


def _load_rate_base() -> None:
    functions = ["transmission", "distribution_electric", "generation", "distribution_gas", "general"]
    # 2025 base rate base by function (USD millions)
    base_2025 = {
        "transmission": 1820,
        "distribution_electric": 2110,
        "generation": 1140,
        "distribution_gas": 980,
        "general": 370,
    }
    rows = []
    for year in range(2020, 2027):
        # 4% growth/yr — back-derive from 2025 base
        growth = 1.04
        delta_years = year - 2025
        factor = growth ** delta_years
        for fn in functions:
            plant = round(base_2025[fn] * factor * 1.55, 2)  # gross plant ≈ 1.55x net for utilities
            accum_depr = round(plant - base_2025[fn] * factor, 2)
            net = round(plant - accum_depr, 2)
            rows.append((year, fn, plant, accum_depr, net))
    sql = (
        f"DELETE FROM {_t('rate_base')}; "
        f"INSERT INTO {_t('rate_base')} (year, function, plant_in_service, accumulated_depr, net_rate_base) "
        f"VALUES {_row_values(rows)}"
    )
    log.info("Loading rate_base (%d rows)", len(rows))
    _sql_exec(sql, timeout_sec=180)


def _load_om() -> None:
    functions = ["transmission", "distribution_electric", "generation", "distribution_gas",
                 "customer_service", "administrative_general"]
    accounts = {
        "transmission": ["562 — operation supervision", "566 — misc transmission", "571 — maintenance"],
        "distribution_electric": ["580 — operation supervision", "583 — overhead lines", "593 — maintenance overhead"],
        "generation": ["546 — fuel handling", "551 — steam expenses", "553 — generation maintenance"],
        "distribution_gas": ["870 — supervision", "874 — mains", "892 — maintenance services"],
        "customer_service": ["903 — customer records", "908 — assistance", "920 — admin & general salaries"],
        "administrative_general": ["920 — admin salaries", "923 — outside services", "926 — pensions & benefits"],
    }
    base_2025 = {
        "transmission": 84.5,
        "distribution_electric": 178.2,
        "generation": 92.0,
        "distribution_gas": 61.4,
        "customer_service": 48.7,
        "administrative_general": 132.3,
    }
    rows: list[tuple] = []
    for year in range(2020, 2027):
        factor = 1.03 ** (year - 2025)
        for fn in functions:
            total = base_2025[fn] * factor
            # Split roughly into the 3 accounts (45/35/20)
            shares = [0.45, 0.35, 0.20]
            for acc, share in zip(accounts[fn], shares):
                rows.append((year, fn, acc, round(total * share, 2)))
    sql = (
        f"DELETE FROM {_t('om_expenses')}; "
        f"INSERT INTO {_t('om_expenses')} (year, function, account, amount) "
        f"VALUES {_row_values(rows)}"
    )
    log.info("Loading om_expenses (%d rows)", len(rows))
    _sql_exec(sql, timeout_sec=180)


def _load_capex() -> None:
    projects = [
        ("Grid Modernization — AMI Refresh", "distribution_electric"),
        ("Grid Modernization — DERMS", "distribution_electric"),
        ("Wildfire Mitigation — Covered Conductor", "distribution_electric"),
        ("Wildfire Mitigation — Undergrounding", "distribution_electric"),
        ("Substation Rebuild Program", "distribution_electric"),
        ("Transmission Line — Aurora-Ridgemont 230kV", "transmission"),
        ("Transmission Line — Three Rivers-Salish 115kV", "transmission"),
        ("Gas Distribution Main Replacement", "distribution_gas"),
        ("Gas Transmission Integrity Management", "distribution_gas"),
        ("Battery Storage — Aurora 50MW", "generation"),
        ("Customer Information System Replacement", "general"),
        ("Fleet Electrification", "general"),
    ]
    rows: list[tuple] = []
    annual_total = {2026: 845, 2027: 902, 2028: 928, 2029: 945, 2030: 962}
    for year in range(2020, 2027):
        # Historical capex grows 3.5%/yr from a 2020 base of 612
        if year < 2026:
            total = round(612 * (1.035 ** (year - 2020)), 1)
            status = "completed" if year < 2025 else "in_progress"
        else:
            total = annual_total[year]
            status = "planned"
        # Distribute among projects unevenly (concentration in dist + grid mod)
        weights = [0.13, 0.10, 0.12, 0.07, 0.09, 0.08, 0.05, 0.09, 0.07, 0.06, 0.08, 0.06]
        for (proj, fn), w in zip(projects, weights):
            rows.append((year, proj, fn, round(total * w, 2), status))
    sql = (
        f"DELETE FROM {_t('capex_plan')}; "
        f"INSERT INTO {_t('capex_plan')} (year, project, function, amount, status) "
        f"VALUES {_row_values(rows)}"
    )
    log.info("Loading capex_plan (%d rows)", len(rows))
    _sql_exec(sql, timeout_sec=180)


def _load_customer_counts(facts: dict) -> None:
    classes = list(facts["customers"]["by_class_2025"].keys())
    base = facts["customers"]["by_class_2025"]
    rows: list[tuple] = []
    for year in range(2020, 2027):
        factor = 1.011 ** (year - 2025)
        for cls in classes:
            customers = int(base[cls] * factor)
            # MWh sales: rough average kWh/customer/yr by class
            kwh_by_class = {
                "residential_electric": 11200,
                "small_commercial_electric": 38000,
                "large_commercial_electric": 720000,
                "industrial_electric": 18500000,
                "residential_gas": 0,
                "small_commercial_gas": 0,
                "large_commercial_gas": 0,
            }
            sales_mwh = round(customers * kwh_by_class.get(cls, 0) / 1000.0, 1)
            rows.append((year, cls, customers, sales_mwh))
    sql = (
        f"DELETE FROM {_t('customer_counts')}; "
        f"INSERT INTO {_t('customer_counts')} (year, class, customers, sales_mwh) "
        f"VALUES {_row_values(rows)}"
    )
    log.info("Loading customer_counts (%d rows)", len(rows))
    _sql_exec(sql, timeout_sec=180)


def _load_billing_determinants(facts: dict) -> None:
    classes = list(facts["customers"]["by_class_2025"].keys())
    rows: list[tuple] = []
    # base 2025 revenue (USD millions) and sales (units = MWh or Dth)
    base = {
        "residential_electric":  {"sales": 6080.0, "revenue": 712.0},
        "small_commercial_electric": {"sales": 2980.0, "revenue": 318.0},
        "large_commercial_electric": {"sales": 6440.0, "revenue": 612.0},
        "industrial_electric":   {"sales": 5780.0, "revenue": 432.0},
        "residential_gas":       {"sales": 32100.0, "revenue": 384.0},   # Dth thousands, revenue $M
        "small_commercial_gas":  {"sales": 9420.0, "revenue": 98.0},
        "large_commercial_gas":  {"sales": 4280.0, "revenue": 41.0},
    }
    for year in range(2020, 2027):
        sales_factor = 1.008 ** (year - 2025)
        rev_factor = 1.025 ** (year - 2025)   # rates outgrow sales
        for cls in classes:
            sales = round(base[cls]["sales"] * sales_factor, 1)
            revenue = round(base[cls]["revenue"] * rev_factor, 1)
            avg_rate = round((revenue * 1_000_000.0) / (sales * 1000.0), 4) if sales else 0.0
            rows.append((year, cls, sales, revenue, avg_rate))
    sql = (
        f"DELETE FROM {_t('billing_determinants')}; "
        f"INSERT INTO {_t('billing_determinants')} (year, class, sales, revenue, average_rate) "
        f"VALUES {_row_values(rows)}"
    )
    log.info("Loading billing_determinants (%d rows)", len(rows))
    _sql_exec(sql, timeout_sec=180)


def _load_roe_history(facts: dict) -> None:
    jurisdiction = "State of Cascadia"
    # ROE per year following the prior orders
    series = [
        (2020, 9.40, 49.5),
        (2021, 9.40, 49.5),
        (2022, 9.40, 49.5),
        (2023, 9.55, 50.0),  # post-2022 GRC settlement
        (2024, 9.55, 50.0),
        (2025, 9.55, 50.0),  # 24-003 confirmed
        (2026, 9.55, 50.0),  # current authorized; pending 26-001
    ]
    rows = [(y, jurisdiction, roe, eq) for (y, roe, eq) in series]
    sql = (
        f"DELETE FROM {_t('roe_history')}; "
        f"INSERT INTO {_t('roe_history')} (year, jurisdiction, authorized_roe, capital_structure_equity_pct) "
        f"VALUES {_row_values(rows)}"
    )
    log.info("Loading roe_history (%d rows)", len(rows))
    _sql_exec(sql, timeout_sec=120)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main_async(args: argparse.Namespace) -> int:
    facts = json.loads((ROOT / "seed" / "nlpg_facts.json").read_text())
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"Manifest not found at {MANIFEST_PATH} — run seed/generate.py first")
    manifest = json.loads(MANIFEST_PATH.read_text())

    if not args.skip_lakebase:
        url = _build_url()
        engine = create_async_engine(
            url,
            connect_args={
                "ssl": "require",
                "server_settings": {"search_path": "rcw,public"},
            },
        )
        try:
            log.info("Upserting cases…")
            case_ids = await _upsert_cases(engine, manifest["cases"])

            log.info("Seeding phases…")
            await _seed_phases(engine, case_ids)

            log.info("Seeding witnesses…")
            await _seed_witnesses(engine, facts["witnesses"])

            log.info("Seeding documents…")
            doc_ids = await _seed_documents(engine, manifest.get("documents", []), case_ids)

            log.info("Seeding knowledge_chunks placeholders…")
            await _seed_knowledge_chunks_placeholders(engine, doc_ids)

            log.info("Seeding data_requests…")
            dr_ids = await _seed_data_requests(engine, manifest.get("data_requests", []), case_ids)

            log.info("Producing realistic DR distribution + witness assignments…")
            async with engine.begin() as conn:
                # 1. All DRs are issued during the **discovery** phase (phase_id reflects
                #    when the DR was issued, not the workflow status of the response).
                await conn.execute(
                    text(
                        "UPDATE data_requests dr SET phase_id = cp.id "
                        "FROM case_phases cp "
                        "WHERE dr.case_id = cp.case_id "
                        "  AND cp.phase_type = 'discovery'"
                    )
                )

                # 2. Round-robin assign every DR to one of the witnesses.
                await conn.execute(
                    text(
                        "WITH w AS ( "
                        "  SELECT id, ROW_NUMBER() OVER (ORDER BY name) - 1 AS idx, "
                        "         COUNT(*) OVER () AS total FROM witnesses "
                        "), "
                        "numbered AS ( "
                        "  SELECT dr.id, ROW_NUMBER() OVER (PARTITION BY dr.case_id ORDER BY dr.dr_number) - 1 AS rn, "
                        "         (SELECT total FROM w LIMIT 1) AS total "
                        "  FROM data_requests dr "
                        ") "
                        "UPDATE data_requests d SET assigned_witness_id = w.id "
                        "FROM numbered n, w "
                        "WHERE d.id = n.id AND w.idx = (n.rn % n.total)"
                    )
                )

                # 3. Realistic status distribution on the ACTIVE case using DR number ordering.
                #    Closed cases stay all-filed (they're historical). The active case ramps:
                #      first 30%  -> new (just arrived)
                #      next 20%   -> assigned
                #      next 20%   -> drafting
                #      next 10%   -> in_review
                #      next 8%    -> approved
                #      last 12%   -> filed (filed early in this case's discovery phase)
                await conn.execute(
                    text(
                        "WITH active_drs AS ( "
                        "  SELECT dr.id, ROW_NUMBER() OVER (ORDER BY dr.dr_number) AS rn, "
                        "         COUNT(*) OVER () AS total "
                        "  FROM data_requests dr JOIN cases c ON c.id = dr.case_id "
                        "  WHERE c.status = 'active' "
                        ") "
                        "UPDATE data_requests d SET status = CASE "
                        "  WHEN n.rn::float / n.total <= 0.30 THEN CAST('new' AS dr_status) "
                        "  WHEN n.rn::float / n.total <= 0.50 THEN CAST('assigned' AS dr_status) "
                        "  WHEN n.rn::float / n.total <= 0.70 THEN CAST('drafting' AS dr_status) "
                        "  WHEN n.rn::float / n.total <= 0.80 THEN CAST('in_review' AS dr_status) "
                        "  WHEN n.rn::float / n.total <= 0.88 THEN CAST('approved' AS dr_status) "
                        "  ELSE CAST('filed' AS dr_status) "
                        "END "
                        "FROM active_drs n WHERE d.id = n.id"
                    )
                )

                # 4. Ensure closed-case DRs are all filed
                await conn.execute(
                    text(
                        "UPDATE data_requests d SET status = CAST('filed' AS dr_status) "
                        "FROM cases c WHERE c.id = d.case_id AND c.status = 'closed' "
                        "  AND d.status <> 'filed'"
                    )
                )

                # 5. Create draft response rows for DRs in drafting/in_review/approved/filed
                #    so the Review Queue, Filing Console, and history have real content.
                await conn.execute(
                    text(
                        "INSERT INTO responses ( "
                        "  data_request_id, version, is_current, draft_text, final_text, "
                        "  status, filed_at "
                        ") "
                        "SELECT d.id, 1, TRUE, "
                        "       'Draft response to ' || d.dr_number || E'\\n\\nSubject: ' || d.subject || "
                        "       E'\\n\\nNorthern Light Power & Gas Company (\"NLPG\" or the \"Company\") respectfully responds as follows. "
                        "       Please see the attached workpapers WP-' || d.dr_number || ' for the supporting calculations.', "
                        "       CASE WHEN d.status IN ('approved','filed') "
                        "            THEN 'Final response to ' || d.dr_number || ' — see attached.' "
                        "            ELSE NULL END, "
                        "       CASE d.status "
                        "         WHEN 'drafting'  THEN CAST('draft' AS response_status) "
                        "         WHEN 'in_review' THEN CAST('in_review' AS response_status) "
                        "         WHEN 'approved'  THEN CAST('approved' AS response_status) "
                        "         WHEN 'filed'     THEN CAST('filed' AS response_status) "
                        "       END, "
                        "       CASE WHEN d.status = 'filed' THEN now() - interval '7 days' ELSE NULL END "
                        "FROM data_requests d "
                        "WHERE d.status IN ('drafting','in_review','approved','filed') "
                        "  AND NOT EXISTS (SELECT 1 FROM responses r WHERE r.data_request_id = d.id)"
                    )
                )

                # 6. Phase statuses — reflect actual progress
                await conn.execute(
                    text(
                        "UPDATE case_phases SET status = CAST('in_progress' AS phase_status) "
                        "FROM cases c WHERE c.id = case_phases.case_id "
                        "  AND c.status = 'active' AND case_phases.phase_type = 'discovery'"
                    )
                )
                await conn.execute(
                    text(
                        "UPDATE case_phases SET status = CAST('closed' AS phase_status) "
                        "FROM cases c WHERE c.id = case_phases.case_id AND c.status = 'closed'"
                    )
                )
                # Active case earlier phases marked closed (already done)
                await conn.execute(
                    text(
                        "UPDATE case_phases SET status = CAST('filed' AS phase_status) "
                        "FROM cases c WHERE c.id = case_phases.case_id "
                        "  AND c.status = 'active' AND case_phases.phase_type IN ('pre_filing','filing')"
                    )
                )

            log.info("Seeding prior responses…")
            await _seed_responses(engine, manifest.get("prior_responses", []), dr_ids)

            log.info("Seeding genie_rooms (if GENIE_SPACE_ID set)…")
            await _seed_genie_room_placeholder(engine)

            await _seed_lifecycle_extras(engine)
        finally:
            await engine.dispose()

    if not args.skip_delta:
        log.info("Creating Delta tables in %s.%s…", CATALOG, TABULAR_SCHEMA)
        _ensure_tabular_schema()
        _create_delta_tables()
        _load_rate_base()
        _load_om()
        _load_capex()
        _load_customer_counts(facts)
        _load_billing_determinants(facts)
        _load_roe_history(facts)

    log.info("seed_db complete")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--skip-lakebase", action="store_true")
    p.add_argument("--skip-delta", action="store_true")
    # Databricks Jobs sometimes passes extra args; ignore unknowns
    args, _ = p.parse_known_args()
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Databricks Jobs runs inside an already-running event loop.
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(main_async(args))
    except RuntimeError:
        pass
    return asyncio.run(main_async(args))


# ---------------------------------------------------------------------------
# Rate-case lifecycle seeds (rebuttal positions, orders, settlements, hearings)
# ---------------------------------------------------------------------------


async def _seed_lifecycle_extras(engine) -> None:
    log.info("Seeding lifecycle: extra cases + positions / orders / settlements / hearings…")
    async with engine.begin() as conn:
        # --- Extra cases at different lifecycle stages ----------------------
        # Make sure we have at least one case per lifecycle stage so the
        # case switcher shows: pre-filing, active (discovery), active (later
        # stage), and closed.
        await conn.execute(
            text(
                "INSERT INTO cases ( "
                "  id, name, docket_number, jurisdiction, commission, utility_name, "
                "  case_type, description, filed_date, target_decision_date, status "
                ") "
                "SELECT gen_random_uuid(), src.name, src.docket, src.jur, src.comm, src.util, "
                "       src.case_type, src.descr, CAST(src.filed AS DATE), CAST(src.target AS DATE), "
                "       CAST(src.status AS case_status) "
                "FROM (VALUES "
                "  ('NLPG 2027 Gas-Only Rate Case','NLPG-27-001','State of Cascadia',"
                "   'Cascadia Public Utilities Commission','Northern Light Power & Gas Company',"
                "   'general_rate_case',"
                "   'Pre-filing for a gas-only revenue requirement update; testimony lineup and exhibits in preparation. Expected filing Q1 2027.',"
                "   '2026-11-15','2027-12-31','pre_filing'),"
                "  ('NLPG 2025 Storm Cost Recovery','NLPG-25-008','State of Cascadia',"
                "   'Cascadia Public Utilities Commission','Northern Light Power & Gas Company',"
                "   'storm_recovery',"
                "   'Storm cost recovery filing seeking deferred cost recovery for the December 2024 ice storms; currently in post-hearing briefs.',"
                "   '2025-03-12','2026-06-30','active'),"
                "  ('NLPG 2020 General Rate Case','NLPG-20-007','State of Cascadia',"
                "   'Cascadia Public Utilities Commission','Northern Light Power & Gas Company',"
                "   'general_rate_case',"
                "   'Completed general rate case from 2020. Final order issued Q1 2021; compliance fully filed. Used as historical reference.',"
                "   '2020-08-04','2021-03-15','closed') "
                ") AS src(name, docket, jur, comm, util, case_type, descr, filed, target, status) "
                "WHERE NOT EXISTS (SELECT 1 FROM cases WHERE docket_number = src.docket)"
            )
        )

        # Ensure phases exist for these new cases
        await conn.execute(
            text(
                "INSERT INTO case_phases (id, case_id, phase_type, sequence, status) "
                "SELECT gen_random_uuid(), c.id, pt.phase_type::phase_type, pt.seq, "
                "       CAST('not_started' AS phase_status) "
                "FROM cases c, (VALUES "
                "  ('pre_filing',1),('filing',2),('discovery',3),('direct_testimony',4),"
                "  ('rebuttal',5),('surrebuttal',6),('hearing',7),('post_hearing_briefs',8),"
                "  ('order',9),('compliance',10) "
                ") AS pt(phase_type, seq) "
                "WHERE c.docket_number IN ('NLPG-27-001','NLPG-25-008','NLPG-20-007') "
                "  AND NOT EXISTS ( "
                "    SELECT 1 FROM case_phases cp "
                "    WHERE cp.case_id = c.id AND cp.phase_type = pt.phase_type::phase_type "
                "  )"
            )
        )

        # NLPG-27-001 (pre-filing): mark pre_filing as in_progress
        await conn.execute(
            text(
                "UPDATE case_phases cp SET status = 'in_progress'::phase_status "
                "FROM cases c WHERE cp.case_id = c.id "
                "  AND c.docket_number = 'NLPG-27-001' AND cp.phase_type = 'pre_filing'"
            )
        )

        # NLPG-25-008 (late stage): mark filing/discovery/direct/rebuttal/hearing as closed,
        # post_hearing_briefs as in_progress
        await conn.execute(
            text(
                "UPDATE case_phases cp SET status = 'closed'::phase_status "
                "FROM cases c WHERE cp.case_id = c.id "
                "  AND c.docket_number = 'NLPG-25-008' "
                "  AND cp.phase_type IN ('pre_filing','filing','discovery','direct_testimony','rebuttal','surrebuttal','hearing')"
            )
        )
        await conn.execute(
            text(
                "UPDATE case_phases cp SET status = 'in_progress'::phase_status "
                "FROM cases c WHERE cp.case_id = c.id "
                "  AND c.docket_number = 'NLPG-25-008' AND cp.phase_type = 'post_hearing_briefs'"
            )
        )

        # NLPG-20-007 (complete): all phases closed
        await conn.execute(
            text(
                "UPDATE case_phases cp SET status = 'closed'::phase_status "
                "FROM cases c WHERE cp.case_id = c.id AND c.docket_number = 'NLPG-20-007'"
            )
        )

        # Add a few DRs to NLPG-25-008 so it has content to demo the late-stage view
        await conn.execute(
            text(
                "INSERT INTO data_requests ( "
                "  id, case_id, phase_id, dr_number, requester, requester_kind, "
                "  issued_date, due_date, subject, body, status, priority, topic_tags "
                ") "
                "SELECT gen_random_uuid(), c.id, cp.id, src.dr_no, src.requester, src.kind, "
                "       CAST(src.issued AS DATE), CAST(src.due AS DATE), src.subject, src.body, "
                "       CAST(src.status AS dr_status), 'normal', ARRAY[]::text[] "
                "FROM cases c "
                "JOIN case_phases cp ON cp.case_id = c.id AND cp.phase_type = 'discovery' "
                ", (VALUES "
                "  ('STAFF-DR-001','CPUC-X Staff','staff','2025-04-10','2025-04-24',"
                "   'Provide all storm restoration invoices over \\$50K','Per Order 25-0182, please provide all individual storm-restoration invoices over \\$50,000.','filed'),"
                "  ('OCA-DR-001','Office of Consumer Advocacy','consumer_advocate','2025-04-12','2025-04-26',"
                "   'Justify deferral accounting','Please justify the use of regulatory asset deferral for the December 2024 storm costs under SFAS 71.','filed'),"
                "  ('STAFF-DR-002','CPUC-X Staff','staff','2025-04-15','2025-04-29',"
                "   'FEMA reimbursements','Identify all federal disaster reimbursements received or expected and how they offset the deferred costs.','filed') "
                ") AS src(dr_no, requester, kind, issued, due, subject, body, status) "
                "WHERE c.docket_number = 'NLPG-25-008' "
                "  AND NOT EXISTS ( "
                "    SELECT 1 FROM data_requests dr WHERE dr.case_id = c.id AND dr.dr_number = src.dr_no "
                "  )"
            )
        )

        # NLPG-20-007: add the final order so the Order page demos a fully-complete case
        await conn.execute(
            text(
                "INSERT INTO commission_orders ( "
                "  id, case_id, order_number, issued_date, effective_date, "
                "  authorized_revenue_increase_m, authorized_roe_pct, authorized_equity_pct, "
                "  capex_approved_m, summary, compliance_filings_due "
                ") "
                "SELECT gen_random_uuid(), c.id, 'Order 21-0091', '2021-01-21', '2021-03-01', "
                "       96.5, 9.40, 50.0, 312.0, "
                "       'CPUC-X authorized a $96.5M revenue increase (vs $135.0M requested), ROE of 9.40% on a 50/50 capital structure. Disallowed $58M of distribution capex. All compliance filings completed by July 2021.', "
                "       '2021-07-31' "
                "FROM cases c "
                "WHERE c.docket_number = 'NLPG-20-007' "
                "  AND NOT EXISTS (SELECT 1 FROM commission_orders co WHERE co.case_id = c.id)"
            )
        )

        # --- Witnesses, testimony + briefs for every case at the right state ---
        # Closed cases: full lifecycle of filed artifacts.
        # Late-stage active case: testimony filed + briefs in progress.
        # Active case (NLPG-26-001): direct testimony already from generate.py;
        # add a couple of in-progress rebuttals so the workflow has content.
        await conn.execute(
            text(
                "INSERT INTO testimony ( "
                "  id, case_id, phase_id, witness_id, kind, title, "
                "  draft_text, final_text, status, filed_at, rebuts_position_ids "
                ") "
                "SELECT gen_random_uuid(), c.id, "
                "       (SELECT id FROM case_phases WHERE case_id = c.id AND phase_type = src.phase::phase_type), "
                "       (SELECT id FROM witnesses ORDER BY name LIMIT 1 OFFSET src.wn), "
                "       CAST(src.kind AS testimony_kind), src.title, NULL, src.body, "
                "       CAST(src.status AS response_status), "
                "       CASE WHEN src.status = 'filed' THEN CAST(src.filed AS TIMESTAMPTZ) ELSE NULL END, "
                "       ARRAY[]::text[] "
                "FROM cases c, (VALUES "
                # --- NLPG-22-005 (closed, GRC, full lifecycle) -----------------
                "  ('NLPG-22-005','direct_testimony','direct',0,"
                "    'Direct Testimony of Brendan O''Sullivan — Revenue Requirements',"
                "    'Q. Please state your name and position.\nA. My name is Brendan O''Sullivan; I am Chief Financial Officer of NLPG.\n\nQ. What is the purpose of your direct testimony?\nA. I support the Company''s overall $142.0M revenue requirement, the proposed capital structure (54/46 equity/debt), and the cash working capital allowance reflected in Schedule WP-2.\n\n[FILED — full text in workpaper WP-2-Revenue-Requirements.pdf]',"
                "    'filed','2022-09-12'),"
                "  ('NLPG-22-005','direct_testimony','direct',1,"
                "    'Direct Testimony of Jonathan Akinwale-Petersen — Depreciation',"
                "    'Q. Please summarize the depreciation study.\nA. We engaged Concentric to refresh the depreciation study using updated Iowa curves. Net-salvage assumptions were revised downward for distribution to reflect actual retirement experience.\n\n[FILED — see Concentric Depreciation Study Exhibit BAP-1]',"
                "    'filed','2022-09-12'),"
                "  ('NLPG-22-005','rebuttal','rebuttal',0,"
                "    'Rebuttal Testimony of Brendan O''Sullivan',"
                "    'Q. Do you agree with Staff''s recommended 9.10% ROE?\nA. No. Staff''s recommendation relies on a DCF analysis with a stale proxy group and ignores recent capital market evidence. The Company maintains its 9.85% recommendation as supported by Dr. Bergstrom''s direct testimony.\n\n[FILED — full text in workpaper WP-R-2-ROE-Rebuttal.pdf]',"
                "    'filed','2023-01-10'),"
                "  ('NLPG-22-005','surrebuttal','surrebuttal',0,"
                "    'Surrebuttal Testimony of Dr. Camille Bergstrom — ROE',"
                "    'Q. OCA has now offered a 9.30% ROE in surrebuttal. Has your view changed?\nA. No. OCA''s revised analysis still excludes flotation costs and uses a non-representative proxy group. My recommended range of 9.75%-10.00% remains supported.\n\n[FILED]',"
                "    'filed','2023-01-31'),"
                "  ('NLPG-22-005','post_hearing_briefs','initial_brief',0,"
                "    'NLPG Initial Brief',"
                "    'I. INTRODUCTION\nNorthern Light Power & Gas Company files this initial brief in support of its Application for a $142.0M revenue increase.\n\nII. REVENUE REQUIREMENTS\nThe record supports the Company''s requested rate base ($5.43B), O&M ($1.94B), and a 9.85% ROE on a 54/46 capital structure.\n\n[FILED — 162 pages]',"
                "    'filed','2023-03-22'),"
                "  ('NLPG-22-005','post_hearing_briefs','reply_brief',0,"
                "    'NLPG Reply Brief',"
                "    'I. RESPONSE TO STAFF\nStaff''s reply mischaracterizes the Concentric depreciation analysis. As shown in Mr. Akinwale-Petersen''s rebuttal, the Iowa curves were refit using NLPG-specific retirement experience…\n\n[FILED — 84 pages]',"
                "    'filed','2023-04-05'),"
                # --- NLPG-24-003 (closed, ROE-only) -----------------------------
                "  ('NLPG-24-003','direct_testimony','direct',4,"
                "    'Direct Testimony of Dr. Camille Bergstrom — ROE Update',"
                "    'Q. Why is the Company seeking a limited-issue ROE update?\nA. Capital market conditions have shifted materially since the 2023 order. Risk-free rates have risen, requiring a corresponding ROE step-up. My analysis supports a 9.85% ROE.\n\n[FILED]',"
                "    'filed','2024-06-14'),"
                "  ('NLPG-24-003','rebuttal','rebuttal',4,"
                "    'Rebuttal Testimony of Dr. Camille Bergstrom',"
                "    'Q. Staff has proposed 9.50%. Why is that insufficient?\nA. Staff''s analysis disregards the equity-risk-premium evidence and uses a forward-looking risk-free rate based on a single auction. My 9.85% recommendation remains supported.\n\n[FILED]',"
                "    'filed','2024-08-22'),"
                "  ('NLPG-24-003','post_hearing_briefs','initial_brief',0,"
                "    'NLPG Initial Brief — ROE Update',"
                "    'I. INTRODUCTION\nThe limited-issue proceeding concerns one question: the appropriate ROE in light of changed capital market conditions.\n\n[FILED — 38 pages]',"
                "    'filed','2024-10-04'),"
                # --- NLPG-20-007 (fully complete historical case) ---------------
                "  ('NLPG-20-007','direct_testimony','direct',0,"
                "    'Direct Testimony — 2020 Revenue Requirements',"
                "    'Q. Please summarize the Company''s 2020 revenue request.\nA. The Company seeks a $135M revenue increase reflecting investment in grid modernization and storm hardening completed since the last case.\n\n[HISTORICAL — full filing preserved]',"
                "    'filed','2020-08-04'),"
                "  ('NLPG-20-007','post_hearing_briefs','initial_brief',0,"
                "    'NLPG 2020 Initial Brief',"
                "    'The record supports the Company''s 2020 rate request. [HISTORICAL].',"
                "    'filed','2020-12-15'),"
                # --- NLPG-25-008 (late stage — storm cost recovery) -------------
                "  ('NLPG-25-008','direct_testimony','direct',1,"
                "    'Direct Testimony of Brendan O''Sullivan — Storm Cost Deferral',"
                "    'Q. Please summarize the storm-related costs the Company seeks to recover.\nA. The December 2024 ice storms caused $87.4M of incremental restoration cost. Per Order 25-0182, those costs were deferred to a regulatory asset, and the Company now seeks amortization recovery over 5 years.\n\n[FILED]',"
                "    'filed','2025-05-20'),"
                "  ('NLPG-25-008','rebuttal','rebuttal',1,"
                "    'Rebuttal Testimony of Brendan O''Sullivan',"
                "    'Q. CIEUC argues storm costs should be absorbed in base rates. Why is deferral appropriate here?\nA. The December 2024 storms exceeded the historical 30-year frequency band — see Exhibit BJS-R-3. Per the Commission''s extraordinary-event criteria, deferral with subsequent amortization is the appropriate cost recovery mechanism.\n\n[FILED]',"
                "    'filed','2025-09-08'),"
                "  ('NLPG-25-008','surrebuttal','surrebuttal',1,"
                "    'Surrebuttal Testimony of Brendan O''Sullivan',"
                "    'Q. OCA''s surrebuttal proposes 7-year amortization. Why is 5 years appropriate?\nA. A 5-year amortization aligns with the average customer-relationship duration in NLPG''s service territory and avoids inter-generational cost shifting. [FILED]',"
                "    'filed','2025-10-20'),"
                "  ('NLPG-25-008','post_hearing_briefs','initial_brief',1,"
                "    'NLPG Storm Cost Recovery — Initial Brief',"
                "    'I. INTRODUCTION\nThe record fully supports recovery of the $87.4M storm-related regulatory asset over 5 years. [DRAFT — 67 pages]',"
                "    'in_review','2026-04-15'),"
                # --- NLPG-26-001 (active mid-stage) — add an in-flight rebuttal -
                "  ('NLPG-26-001','rebuttal','rebuttal',4,"
                "    'Rebuttal Testimony of Dr. Camille Bergstrom — ROE (DRAFT)',"
                "    'Q. Staff recommends a 9.25% ROE — 85 bps below the Company''s 10.10%. What is your response?\nA. Staff''s proxy group excludes three comparable utilities with similar risk profiles. When those are added back, the indicated ROE is in the 9.95%-10.20% range. [DRAFT — to be finalized after surrebuttal evidence]',"
                "    'draft','2026-06-15') "
                ") AS src(docket, phase, kind, wn, title, body, status, filed) "
                "WHERE c.docket_number = src.docket "
                "  AND NOT EXISTS ( "
                "    SELECT 1 FROM testimony t "
                "    WHERE t.case_id = c.id AND t.title = src.title "
                "  )"
            )
        )

        # Per-case documents (so Knowledge Library shows real content on closed cases)
        await conn.execute(
            text(
                "INSERT INTO documents ( "
                "  id, case_id, title, kind, uri, page_count, classification, "
                "  ingested_at, indexed_at, summary, topic_tags "
                ") "
                "SELECT gen_random_uuid(), c.id, src.title, "
                "       CAST(src.kind AS document_kind), "
                "       '/Volumes/grid_ops_demo_catalog/rcw_knowledge/docs_raw/' || c.docket_number || '/' || src.subdir || '/' || src.fname, "
                "       src.pages, CAST(src.cls AS classification), "
                "       NOW() - interval '30 days', NOW() - interval '30 days', "
                "       src.summary, ARRAY[]::text[] "
                "FROM cases c, (VALUES "
                "  ('NLPG-22-005','Application of NLPG — 2022 General Rate Case','filing','filing','application-of-nlpg-2022-grc.txt',412,'public',"
                "    'Application of Northern Light Power & Gas Company for a $142.0M general rate increase, filed 2022-08-04.'),"
                "  ('NLPG-22-005','Direct Testimony of Brendan O''Sullivan — 2022 GRC','testimony','testimony','direct-testimony-of-brendan-osullivan-2022.txt',88,'public',"
                "    'CFO direct testimony supporting the $142.0M revenue request and 54/46 capital structure.'),"
                "  ('NLPG-22-005','Rebuttal Testimony of Brendan O''Sullivan — 2022 GRC','testimony','testimony','rebuttal-testimony-of-brendan-osullivan-2022.txt',72,'public',"
                "    'Rebuttal testimony responding to Staff''s 9.10% ROE recommendation.'),"
                "  ('NLPG-22-005','Surrebuttal of Dr. Camille Bergstrom — ROE','testimony','testimony','surrebuttal-testimony-of-bergstrom-2022.txt',54,'public',"
                "    'Surrebuttal on ROE addressing OCA''s 9.30% counter-recommendation.'),"
                "  ('NLPG-22-005','NLPG Initial Brief — 2022 GRC','briefs','filing','nlpg-initial-brief-2022.txt',162,'public',"
                "    'NLPG initial post-hearing brief — 162 pages summarizing the record.'),"
                "  ('NLPG-22-005','NLPG Reply Brief — 2022 GRC','briefs','filing','nlpg-reply-brief-2022.txt',84,'public',"
                "    'NLPG reply brief — responses to opposing initial briefs.'),"
                "  ('NLPG-22-005','Hearing Exhibit Binder — 2022 GRC','hearing','exhibit','hearing-exhibit-binder-2022.txt',324,'confidential',"
                "    'Combined hearing exhibit binder for the evidentiary hearings on March 8 2023.'),"
                "  ('NLPG-24-003','Direct Testimony of Bergstrom — ROE Update','testimony','testimony','direct-testimony-of-bergstrom-roe-2024.txt',62,'public',"
                "    'ROE update testimony supporting 9.85% based on capital market conditions.'),"
                "  ('NLPG-24-003','NLPG Initial Brief — ROE Proceeding','briefs','filing','nlpg-roe-initial-brief-2024.txt',38,'public',"
                "    'NLPG initial brief on ROE update — 38 pages.'),"
                "  ('NLPG-20-007','Application of NLPG — 2020 General Rate Case','filing','filing','application-of-nlpg-2020-grc.txt',396,'public',"
                "    'Historical 2020 NLPG general rate case application — preserved for reference.'),"
                "  ('NLPG-20-007','NLPG Initial Brief — 2020 GRC','briefs','filing','nlpg-2020-initial-brief.txt',148,'public',"
                "    'NLPG 2020 initial brief.'),"
                "  ('NLPG-25-008','Storm Cost Recovery — Application','filing','filing','storm-cost-deferral-application.txt',114,'public',"
                "    'Storm cost recovery application — $87.4M regulatory asset from December 2024 ice storms.'),"
                "  ('NLPG-25-008','Direct Testimony — Storm Cost Recovery','testimony','testimony','direct-testimony-storm-recovery.txt',54,'public',"
                "    'Direct testimony supporting the storm-cost deferral and 5-year amortization.'),"
                "  ('NLPG-25-008','Rebuttal Testimony — Storm Cost Recovery','testimony','testimony','rebuttal-testimony-storm-recovery.txt',38,'public',"
                "    'Rebuttal testimony addressing CIEUC''s base-rate absorption argument.') "
                ") AS src(docket, title, subdir, kind, fname, pages, cls, summary) "
                "WHERE c.docket_number = src.docket "
                "  AND NOT EXISTS ( "
                "    SELECT 1 FROM documents d "
                "    WHERE d.case_id = c.id AND d.title = src.title "
                "  )"
            )
        )

        # --- Existing lifecycle artifacts (positions, orders, settlements, hearings) ----
        # Intervenor positions — only for the active case (NLPG-26-001)
        await conn.execute(
            text(
                "INSERT INTO intervenor_positions "
                "(id, case_id, intervenor, intervenor_kind, topic, position_text, "
                " source_citation, proposed_adjustment, impact_amount_m, filed_date, status) "
                "SELECT gen_random_uuid(), c.id, src.intervenor, src.kind, src.topic, src.text, "
                "       src.citation, src.adjustment, src.impact_m, "
                "       CAST(src.filed_date AS DATE), 'open' "
                "FROM cases c, (VALUES "
                "  ('CPUC-X Staff','staff','Return on equity',"
                "   'Staff recommends 9.25% ROE — 85 bps below the Company''s 10.10% — based on the comparable-utility DCF analysis in Staff Exhibit S-3.',"
                "   'Staff Direct (Lin), p.18','Reduce ROE from 10.10% to 9.25%',-22.4,'2026-04-12'),"
                "  ('Office of Consumer Advocacy','consumer_advocate','Capital structure',"
                "   'OCA recommends 50/50 equity/debt instead of the Company''s 54/46, reflecting national averages for comparable utilities.',"
                "   'OCA Direct (Hassan), p.22','Cap equity ratio at 50%',-9.8,'2026-04-15'),"
                "  ('Office of Consumer Advocacy','consumer_advocate','Depreciation rates',"
                "   'OCA opposes the proposed 12% increase in distribution depreciation rates; Iowa curves should be re-fit with newer data showing longer service lives.',"
                "   'OCA Direct (Park), p.11','Hold 2024 depreciation rates flat',-14.6,'2026-04-15'),"
                "  ('Cascadia Industrial Energy Users Coalition','industrial','Cost of service allocation',"
                "   'CIEUC argues the proposed demand allocator over-recovers from industrial classes by failing to apply minimum-distribution-system adjustments.',"
                "   'CIEUC Direct (Volkov), p.7','Shift $6.2M cost responsibility from industrial to residential class',NULL,'2026-04-18'),"
                "  ('Cascadia Climate Action Coalition','environmental','Capex prudence',"
                "   'CCAC opposes the $480M gas distribution main replacement program as imprudent in light of state decarbonization targets.',"
                "   'CCAC Direct (Reeves), p.14','Disallow $120M of FY26 gas main replacement capex',-18.0,'2026-04-20'),"
                "  ('CPUC-X Staff','staff','Rate design',"
                "   'Staff supports the proposed residential rate redesign but recommends a slower 3-year glidepath to the new tier structure to mitigate bill shock.',"
                "   'Staff Direct (Lin), p.31','Phase rate design over 3 years instead of 1',NULL,'2026-04-12'),"
                "  ('Cascadia Industrial Energy Users Coalition','industrial','Storm cost recovery',"
                "   'CIEUC opposes the proposed storm cost recovery rider, arguing storm costs are a routine cost of business and should remain in base rates.',"
                "   'CIEUC Direct (Volkov), p.19','Remove storm rider; absorb in base rates',NULL,'2026-04-18') "
                ") AS src(intervenor, kind, topic, text, citation, adjustment, impact_m, filed_date) "
                "WHERE c.docket_number = 'NLPG-26-001' "
                "  AND NOT EXISTS ( "
                "    SELECT 1 FROM intervenor_positions ip "
                "    WHERE ip.case_id = c.id AND ip.intervenor = src.intervenor AND ip.topic = src.topic "
                "  )"
            )
        )

        # Commission orders for closed cases
        await conn.execute(
            text(
                "INSERT INTO commission_orders "
                "(id, case_id, order_number, issued_date, effective_date, "
                " authorized_revenue_increase_m, authorized_roe_pct, authorized_equity_pct, "
                " capex_approved_m, summary, compliance_filings_due) "
                "SELECT gen_random_uuid(), c.id, src.order_no, CAST(src.issued AS DATE), CAST(src.effective AS DATE), "
                "       src.rev_m, src.roe, src.eq_pct, src.capex_m, src.summary, "
                "       CAST(src.compliance_due AS DATE) "
                "FROM cases c, (VALUES "
                "  ('NLPG-22-005','Order 22-1184','2023-04-18','2023-05-01',"
                "   118.2, 9.55, 52.0, 380.0,"
                "   'CPUC-X authorized a $118.2M revenue increase (vs $142.0M requested), ROE of 9.55% on a 52/48 capital structure. Disallowed $42M of gas capex and ordered a depreciation study refresh by Q4 2024.',"
                "   '2023-09-30'),"
                "  ('NLPG-24-003','Order 24-0772','2024-11-08','2024-12-01',"
                "   28.4, 9.70, 52.5, 0.0,"
                "   'CPUC-X authorized a 15 bps ROE step-up to 9.70% pursuant to the ROE-only proceeding, recognizing increased capital costs. No capex review.',"
                "   '2025-03-31') "
                ") AS src(docket, order_no, issued, effective, rev_m, roe, eq_pct, capex_m, summary, compliance_due) "
                "WHERE c.docket_number = src.docket "
                "  AND NOT EXISTS (SELECT 1 FROM commission_orders co WHERE co.case_id = c.id)"
            )
        )

        # Settlement attempt on NLPG-22-005 (failed → went to hearing)
        await conn.execute(
            text(
                "INSERT INTO settlements "
                "(id, case_id, summary, parties, proposed_revenue_increase_m, proposed_roe_pct, "
                " status, proposed_date, decision_date, full_text) "
                "SELECT gen_random_uuid(), c.id, src.summary, CAST(src.parties AS TEXT[]), "
                "       src.rev_m, src.roe, src.status, "
                "       CAST(src.proposed_date AS DATE), CAST(src.decision_date AS DATE), src.full_text "
                "FROM cases c, (VALUES "
                "  ('NLPG-22-005',"
                "   'Joint stipulation among NLPG, Staff, and OCA proposing a $122M revenue increase + 9.65% ROE on 51/49 capital structure. Rejected by Industrial intervenors over cost-of-service allocation. Case proceeded to hearing.',"
                "   ARRAY['NLPG','CPUC-X Staff','Office of Consumer Advocacy']::TEXT[],"
                "   122.0, 9.65, 'rejected', '2023-01-22', '2023-02-14',"
                "   'Settlement filed Jan 22 2023; rejected by ALJ on Feb 14 after CIEUC opposition. Parties returned to litigation.') "
                ") AS src(docket, summary, parties, rev_m, roe, status, proposed_date, decision_date, full_text) "
                "WHERE c.docket_number = src.docket "
                "  AND NOT EXISTS (SELECT 1 FROM settlements s WHERE s.case_id = c.id)"
            )
        )

        # Hearings — past for closed cases, upcoming for active
        await conn.execute(
            text(
                "INSERT INTO hearings "
                "(id, case_id, title, hearing_date, location, presiding_alj, "
                " witness_lineup, topics, status) "
                "SELECT gen_random_uuid(), c.id, src.title, CAST(src.hd AS DATE), src.loc, src.alj, "
                "       CAST(src.witnesses AS TEXT[]), CAST(src.topics AS TEXT[]), src.status "
                "FROM cases c, (VALUES "
                "  ('NLPG-26-001','Technical hearing — Revenue requirements','2026-07-14',"
                "   'Capitol Hearing Room A, Cascadia City','ALJ Diana Whitfield',"
                "   ARRAY['Helena Marchetti-Yamamoto','Brendan O''Sullivan','Camille Bergstrom']::TEXT[],"
                "   ARRAY['rate base','cost of service','ROE']::TEXT[],'scheduled'),"
                "  ('NLPG-26-001','Public input hearing','2026-06-22',"
                "   'Cascadia City Community College','ALJ Diana Whitfield',"
                "   ARRAY[]::TEXT[],ARRAY['public comment']::TEXT[],'scheduled'),"
                "  ('NLPG-26-001','Cross-examination — Depreciation & Capex','2026-07-28',"
                "   'Capitol Hearing Room A','ALJ Diana Whitfield',"
                "   ARRAY['Jonathan Akinwale-Petersen','Rajesh Kothapalli-Nielsen']::TEXT[],"
                "   ARRAY['depreciation rates','capex prudence']::TEXT[],'scheduled'),"
                "  ('NLPG-22-005','Final evidentiary hearing','2023-03-08',"
                "   'Capitol Hearing Room A','ALJ Marcus Chen',"
                "   ARRAY['Predecessor CFO','Predecessor Rate Design']::TEXT[],"
                "   ARRAY['all issues']::TEXT[],'completed') "
                ") AS src(docket, title, hd, loc, alj, witnesses, topics, status) "
                "WHERE c.docket_number = src.docket "
                "  AND NOT EXISTS ( "
                "    SELECT 1 FROM hearings h WHERE h.case_id = c.id AND h.title = src.title "
                "  )"
            )
        )


if __name__ == "__main__":  # pragma: no cover
    rc = main()
    if rc != 0:
        raise SystemExit(rc)
