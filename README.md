# Rate Case Workbench

End-to-end Databricks App for utility rate case workflow management. Built on Lakebase, Vector Search, Foundation Model APIs, Mosaic Agent Framework, and Genie.

## What it does

Walks regulatory affairs teams through the full lifecycle of a utility rate case:

- **Case hierarchy**: Cases → Phases (pre-filing, filing, discovery, direct testimony, rebuttal, surrebuttal, hearing, briefs, order, compliance).
- **Discovery workflow**: Receive, assign, draft, review, approve, and file data request responses.
- **Agent memory**: Drafting agent remembers positions taken on prior responses in the same case AND prior cases in the same jurisdiction — enforces position consistency.
- **Knowledge library**: Upload case docs, prior orders, internal policies; indexed in Vector Search.
- **Testimony studio**: Draft direct, rebuttal, and surrebuttal testimony with agent assistance.
- **Genie integration**: Query tabular evidence (rate base, capex, O&M, billing) and pin results to draft responses.
- **Admin portal**: Manage cases, users, roles, models, knowledge sources, feature flags, audit.

## Stack

- Backend: FastAPI + SQLAlchemy + Alembic + asyncpg
- Database: Lakebase Postgres (`rcw-lakebase`)
- AI: Mosaic Agent Framework + Foundation Model API (Claude Sonnet 4.6)
- Retrieval: Databricks Vector Search (`rcw-vs` endpoint, managed embeddings)
- Tabular evidence: Genie space over Delta tables in `grid_ops_demo_catalog.rcw_tabular`
- Audit: Delta tables in `grid_ops_demo_catalog.rcw_audit` (CDC nightly from Lakebase)
- Frontend: React + Vite + Tailwind + shadcn/ui + TanStack Router/Query
- Deployment: Databricks App on `fevm-grid-ops-demo`

## Resources (UC-governed)

| Resource | Name | Notes |
|---|---|---|
| Catalog | `grid_ops_demo_catalog` | Shared |
| Schemas | `rcw_app`, `rcw_knowledge`, `rcw_audit`, `rcw_tabular` | |
| Lakebase instance | `rcw-lakebase` | PG16, CU_1 |
| Vector Search endpoint | `rcw-vs` | Standard |
| Volume | `rcw_knowledge.docs_raw` | Raw uploads |
| Warehouse | `Serverless Starter Warehouse` | id `7fb5ec85684023e6` |

## Deploy

```bash
# Sync source to workspace
databricks sync . /Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench \
  --exclude node_modules --exclude .venv --exclude "frontend/src" --exclude "frontend/public" \
  --profile=fe-vm-grid-ops-demo

# Build frontend first
cd frontend && npm install && npm run build && cd ..

# Deploy
databricks apps deploy rate-case-workbench \
  --source-code-path /Workspace/Users/drew.triplett@databricks.com/databricks_apps/rate-case-workbench \
  --profile=fe-vm-grid-ops-demo
```
