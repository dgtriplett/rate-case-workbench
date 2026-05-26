"""FastAPI factory for the Rate Case Workbench app."""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text

from .config import get_settings
from .db import session_scope, shutdown_db
from .models import Base, Role, RoleKey
from .routers import (
    agent,
    alj_recommendation,
    application_workbench,
    automation,
    calendar as calendar_router,
    cases,
    checklist,
    compliance,
    cross_case,
    data_requests,
    document_view,
    documents,
    drafts,
    hearing_prep,
    hearings,
    intervenor_testimony,
    knowledge,
    memory,
    notifications,
    orders,
    parties,
    phases,
    portfolio,
    positions_ledger,
    presence,
    public_comments,
    public_notice,
    rebuttal,
    responses,
    settlements,
    sparky,
    testimony,
    users as users_router,
    witness_coverage,
    witnesses,
)
from .routers import webhook
from .routers.admin import (
    audit as admin_audit,
    cases as admin_cases,
    feature_flags as admin_feature_flags,
    genie as admin_genie,
    integrations as admin_integrations,
    knowledge_sources as admin_knowledge_sources,
    models as admin_models,
    phase_templates as admin_phase_templates,
    settings as admin_settings,
    users as admin_users,
)

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
)
log = logging.getLogger(__name__)


async def _bootstrap_schema() -> None:
    """Idempotent: create dedicated schema, tables, and seed role rows on startup."""
    from .db import _lakebase  # noqa
    sm = await _lakebase.ensure()
    # Create our own schema owned by the connecting role (the app SP)
    async with sm() as session:
        try:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        except Exception:
            log.warning("pgcrypto extension create skipped (insufficient privilege)")
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS rcw"))
        await session.execute(text("SET search_path TO rcw, public"))
        await session.commit()

    engine = _lakebase._engine
    assert engine is not None
    # Set default schema on the engine so create_all uses it
    async with engine.begin() as conn:
        await conn.execute(text("SET search_path TO rcw, public"))
        await conn.run_sync(Base.metadata.create_all)

    # Apply DB-side defaults for UUID primary keys so raw-SQL inserts work
    # (SQLAlchemy's Python-side `default=uuid.uuid4` only applies via the ORM).
    async with session_scope() as session:
        await session.execute(text("SET search_path TO rcw, public"))
        uuid_pk_tables = [
            "users", "user_roles", "cases", "case_phases", "witnesses",
            "data_requests", "responses", "response_citations", "testimony",
            "documents", "knowledge_chunks", "agent_memory", "approvals",
            "comments", "settings", "model_configs", "feature_flags",
            "genie_rooms", "vector_indices", "events",
            "intervenor_positions", "commission_orders", "settlements", "hearings",
            "cross_exam_qa", "compliance_filings", "automation_rules", "presence_records",
            "application_packages", "financial_schedules", "cost_of_service_studies",
            "rate_design_proposals", "parties", "public_comments",
            "alj_recommendations", "intervenor_testimony", "public_notices",
        ]
        for tbl in uuid_pk_tables:
            try:
                await session.execute(
                    text(f"ALTER TABLE {tbl} ALTER COLUMN id SET DEFAULT gen_random_uuid()")
                )
            except Exception as e:
                log.debug("default already set or table missing for %s: %s", tbl, e)
        # Default empty arrays for NOT NULL array columns so raw-SQL inserts work
        array_defaults = [
            ("witnesses", "expertise_areas"),
            ("data_requests", "topic_tags"),
            ("responses", "privilege_flags"),
            ("documents", "topic_tags"),
            ("genie_rooms", "allowed_roles"),
            ("testimony", "rebuts_position_ids"),
            ("settlements", "parties"),
            ("hearings", "witness_lineup"),
            ("hearings", "topics"),
            ("cost_of_service_studies", "source_uc_tables"),
            ("public_comments", "topic_tags"),
            ("alj_recommendations", "positions_adopted"),
            ("alj_recommendations", "positions_rejected"),
            ("intervenor_testimony", "topics"),
            ("public_notices", "channels"),
        ]

        # Add columns added to existing tables after their initial creation.
        # `Base.metadata.create_all` does not ALTER existing tables.
        add_columns = [
            ("testimony", "rebuts_position_ids", "TEXT[]"),
            ("data_requests", "direction", "VARCHAR(16) DEFAULT 'inbound'"),
            ("data_requests", "target_party_id", "UUID"),
            ("hearings", "kind", "VARCHAR(32) DEFAULT 'evidentiary'"),
            ("public_comments", "platform", "VARCHAR(32)"),
            ("public_comments", "source_handle", "VARCHAR(128)"),
        ]
        for tbl, col, coltype in add_columns:
            try:
                await session.execute(
                    text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {coltype}")
                )
            except Exception as e:
                log.warning("ADD COLUMN %s.%s failed: %s", tbl, col, e)

        # Add new enum values that may have been added since the type was created.
        # Postgres requires explicit ALTER TYPE ... ADD VALUE.
        enum_additions = [
            ("testimony_kind", "initial_brief"),
            ("testimony_kind", "reply_brief"),
        ]
        for enum_name, value in enum_additions:
            try:
                await session.execute(
                    text(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
                )
            except Exception as e:
                log.warning("ADD ENUM VALUE %s.%s failed: %s", enum_name, value, e)
        for tbl, col in array_defaults:
            try:
                await session.execute(
                    text(f"ALTER TABLE {tbl} ALTER COLUMN {col} SET DEFAULT ARRAY[]::text[]")
                )
            except Exception as e:
                log.debug("array default not applied for %s.%s: %s", tbl, col, e)

    async with session_scope() as session:
        await session.execute(text("SET search_path TO rcw, public"))
        from sqlalchemy import select
        existing = await session.execute(select(Role.key))
        existing_keys = {r[0] for r in existing.all()}
        for rk in RoleKey:
            if rk not in existing_keys:
                session.add(Role(key=rk, description=rk.value.replace("_", " ").title()))
        log.info("Schema bootstrap complete (schema=rcw)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    log.info("Starting rate-case-workbench (catalog=%s, vs=%s)", s.catalog, s.vs_endpoint)
    if os.environ.get("RCW_SKIP_BOOTSTRAP") != "1":
        try:
            await _bootstrap_schema()
        except Exception:
            log.exception("Schema bootstrap failed (continuing)")
    yield
    await shutdown_db()


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(title="Rate Case Workbench", version="2.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    async def health() -> dict:
        return {"status": "ok", "catalog": s.catalog, "vs_endpoint": s.vs_endpoint}

    api_prefix = "/api/v1"
    app.include_router(users_router.router, prefix=api_prefix)
    app.include_router(cases.router, prefix=api_prefix)
    app.include_router(phases.router, prefix=api_prefix)
    app.include_router(data_requests.router, prefix=api_prefix)
    app.include_router(responses.router, prefix=api_prefix)
    app.include_router(testimony.router, prefix=api_prefix)
    app.include_router(witnesses.router, prefix=api_prefix)
    app.include_router(documents.router, prefix=api_prefix)
    app.include_router(knowledge.router, prefix=api_prefix)
    app.include_router(memory.router, prefix=api_prefix)
    app.include_router(agent.router, prefix=api_prefix)
    app.include_router(sparky.router, prefix=api_prefix)
    app.include_router(notifications.router, prefix=api_prefix)
    app.include_router(webhook.router, prefix=api_prefix)
    app.include_router(checklist.router, prefix=api_prefix)
    app.include_router(document_view.router, prefix=api_prefix)
    app.include_router(rebuttal.router, prefix=api_prefix)
    app.include_router(orders.router, prefix=api_prefix)
    app.include_router(settlements.router, prefix=api_prefix)
    app.include_router(hearings.router, prefix=api_prefix)
    app.include_router(drafts.router, prefix=api_prefix)
    app.include_router(witness_coverage.router, prefix=api_prefix)
    app.include_router(calendar_router.router, prefix=api_prefix)
    app.include_router(positions_ledger.router, prefix=api_prefix)
    app.include_router(cross_case.router, prefix=api_prefix)
    app.include_router(hearing_prep.router, prefix=api_prefix)
    app.include_router(compliance.router, prefix=api_prefix)
    app.include_router(portfolio.router, prefix=api_prefix)
    app.include_router(automation.router, prefix=api_prefix)
    app.include_router(presence.router, prefix=api_prefix)
    app.include_router(application_workbench.router, prefix=api_prefix)
    app.include_router(parties.router, prefix=api_prefix)
    app.include_router(public_comments.router, prefix=api_prefix)
    app.include_router(alj_recommendation.router, prefix=api_prefix)
    app.include_router(intervenor_testimony.router, prefix=api_prefix)
    app.include_router(public_notice.router, prefix=api_prefix)

    admin_prefix = "/api/v1/admin"
    app.include_router(admin_cases.router, prefix=admin_prefix)
    app.include_router(admin_users.router, prefix=admin_prefix)
    app.include_router(admin_models.router, prefix=admin_prefix)
    app.include_router(admin_settings.router, prefix=admin_prefix)
    app.include_router(admin_feature_flags.router, prefix=admin_prefix)
    app.include_router(admin_knowledge_sources.router, prefix=admin_prefix)
    app.include_router(admin_genie.router, prefix=admin_prefix)
    app.include_router(admin_phase_templates.router, prefix=admin_prefix)
    app.include_router(admin_integrations.router, prefix=admin_prefix)
    app.include_router(admin_audit.router, prefix=admin_prefix)

    @app.exception_handler(404)
    async def _api_404(request, exc):
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        return await serve_spa(request)

    frontend_dir = Path(__file__).resolve().parent.parent / "frontend" / "dist"
    if frontend_dir.exists():
        app.mount(
            "/assets",
            StaticFiles(directory=str(frontend_dir / "assets")),
            name="assets",
        )

        @app.get("/{full_path:path}")
        async def serve_spa(full_path: str = "") -> FileResponse:
            index = frontend_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return JSONResponse({"detail": "frontend not built"}, status_code=404)
    else:
        log.warning("frontend/dist not present; serving API only")

    return app


app = create_app()
