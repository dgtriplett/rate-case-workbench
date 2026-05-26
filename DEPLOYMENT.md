# Deployment Guide — Rate Case Workbench

Step-by-step instructions to deploy a fresh copy of this app to **your own**
Databricks workspace, with **or without** the bundled NLPG synthetic dataset.

This guide assumes zero prior familiarity with the codebase.

---

## TL;DR

Two paths from the same starting point:

| Path | Outcome | Time |
|---|---|---|
| **A. With synthetic data** | Identical-looking demo to ours, with the fictional NLPG utility seeded across 6 cases in different lifecycle stages. Best for showing the platform to stakeholders. | ~60-90 min (waits for LLM generation) |
| **B. With your own data** | Empty app shell wired to your workspace. You create your first case via the Admin → Cases UI and start uploading your own documents / DRs. | ~30-40 min |

Both paths share the **Prerequisites → Provisioning → Deploy** sections. They
diverge only at the **Seed** step.

---

## 0. Prerequisites

You need:

1. **A Databricks workspace** that supports:
   - **Lakebase** (Postgres-on-Databricks) — workspace must be in a region with the feature enabled
   - **Vector Search** — most workspaces have this
   - **Foundation Model APIs** — workspaces with Pay-Per-Token enabled (the default in most regions)
   - **Genie** — for the tabular-evidence Q&A (optional but recommended)
2. **Databricks CLI 0.235+** authenticated to that workspace
   ```bash
   brew install databricks    # or your equivalent
   databricks auth login --host https://<your-workspace>.cloud.databricks.com --profile myprofile
   ```
   Verify: `databricks auth profiles | grep myprofile` should say `YES`.
3. **`gh` CLI** to clone the repo (or just `git`)
4. **Python 3.10+** locally (only used to invoke the CLI; the app runs in Databricks)

You do **not** need npm/node locally — the frontend is built on Databricks compute by a Job we provide.

> Substitute `myprofile` with your real CLI profile name in every command below.

---

## 1. Clone the repo

```bash
git clone https://github.com/dgtriplett/rate-case-workbench.git
cd rate-case-workbench
```

---

## 2. Provision the Databricks resources (one-time)

You'll create: 1 Lakebase instance, 1 Vector Search endpoint, 4 UC schemas, 1 UC Volume.

These commands assume you have permission to create UC catalogs/schemas, Lakebase instances, and Vector Search endpoints. Most workspace admins do; if you don't, ask yours to run this section.

> **Pick a catalog and schemas now.** The defaults below use `grid_ops_demo_catalog.rcw_*`. If you want a different catalog/schema layout, set the env vars in `app.yaml` accordingly (see step 5).

```bash
PROFILE=myprofile
CATALOG=grid_ops_demo_catalog     # change to your catalog
WAREHOUSE_ID=$(databricks warehouses list --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)[0]['id'])")
echo "Using warehouse: $WAREHOUSE_ID"

# 2a. Create the Lakebase instance
databricks database create-database-instance \
  --json '{"name": "rcw-lakebase", "capacity": "CU_1", "pg_version": "PG_VERSION_16"}' \
  --profile=$PROFILE

# 2b. Create the 4 UC schemas (catalog itself must already exist)
for SCHEMA in rcw_app rcw_knowledge rcw_audit rcw_tabular; do
  databricks api post /api/2.0/sql/statements --profile=$PROFILE --json "{\"warehouse_id\":\"$WAREHOUSE_ID\",\"statement\":\"CREATE SCHEMA IF NOT EXISTS $CATALOG.$SCHEMA\",\"wait_timeout\":\"30s\"}" | python3 -c "import json,sys; print(sys.argv[1], json.load(sys.stdin)['status']['state'])" -- "$SCHEMA"
done

# 2c. Create the UC Volume for raw uploads
databricks api post /api/2.0/sql/statements --profile=$PROFILE --json "{\"warehouse_id\":\"$WAREHOUSE_ID\",\"statement\":\"CREATE VOLUME IF NOT EXISTS $CATALOG.rcw_knowledge.docs_raw\",\"wait_timeout\":\"30s\"}"

# 2d. Create the Vector Search endpoint
databricks vector-search-endpoints create-endpoint \
  --json '{"name": "rcw-vs", "endpoint_type": "STANDARD"}' \
  --profile=$PROFILE
# wait ~3-5 min for it to come ONLINE
```

Verify everything is up:
```bash
databricks database list-database-instances --profile=$PROFILE | grep rcw-lakebase   # should show state AVAILABLE
databricks vector-search-endpoints list-endpoints --profile=$PROFILE | grep rcw-vs   # state ONLINE
```

---

## 3. Sync code to your workspace

```bash
WORKSPACE_USER=$(databricks current-user me --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['userName'])")
WORKSPACE_PATH="/Workspace/Users/$WORKSPACE_USER/databricks_apps/rate-case-workbench"

databricks sync . "$WORKSPACE_PATH" \
  --exclude node_modules --exclude .venv --exclude __pycache__ --exclude .git \
  --full --profile=$PROFILE
```

This copies the source tree to your workspace. The app will deploy from this path.

---

## 4. Configure `app.yaml` for your workspace

Open `app.yaml` and update the `env:` block if your catalog/schema names differ from the defaults:

```yaml
env:
  - name: CATALOG
    value: <your_catalog>                # default: grid_ops_demo_catalog
  - name: APP_SCHEMA
    value: rcw_app
  - name: KNOWLEDGE_SCHEMA
    value: rcw_knowledge
  - name: AUDIT_SCHEMA
    value: rcw_audit
  - name: TABULAR_SCHEMA
    value: rcw_tabular
  - name: VS_ENDPOINT
    value: rcw-vs
  - name: DRAFTER_MODEL
    value: databricks-claude-sonnet-4-6   # or any FM endpoint you've subscribed to
  - name: SUMMARIZER_MODEL
    value: databricks-claude-haiku-4-5
  - name: EMBEDDING_MODEL
    value: databricks-gte-large-en
  - name: DOCS_VOLUME
    value: /Volumes/<catalog>/rcw_knowledge/docs_raw
```

Re-sync after editing:
```bash
databricks sync . "$WORKSPACE_PATH" --exclude node_modules --exclude .venv \
  --exclude __pycache__ --exclude .git --profile=$PROFILE
```

Also open `backend/auth.py` and set `RCW_ADMIN_EMAILS` in your app's env to include your email so you auto-get admin role on first login:

```yaml
# Add to app.yaml env: section
  - name: RCW_ADMIN_EMAILS
    value: you@yourcompany.com
```

---

## 5. Create the app and bind resources

```bash
# 5a. Create the app shell
databricks apps create rate-case-workbench \
  --description "End-to-end utility rate case workflow" \
  --profile=$PROFILE

# 5b. Capture the URL and service principal
APP_URL=$(databricks apps get rate-case-workbench --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['url'])")
SP=$(databricks apps get rate-case-workbench --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['service_principal_client_id'])")
echo "App URL: $APP_URL"
echo "Service principal: $SP"
```

**Bind resources** — this auto-grants the app SP permission on each:

```bash
cat > /tmp/app-res.json <<EOF
{
  "resources": [
    {"name":"lakebase","description":"Lakebase Postgres",
     "database":{"database_name":"databricks_postgres","instance_name":"rcw-lakebase","permission":"CAN_CONNECT_AND_CREATE"}},
    {"name":"sql-warehouse","description":"SQL warehouse",
     "sql_warehouse":{"id":"$WAREHOUSE_ID","permission":"CAN_USE"}},
    {"name":"drafter-model","description":"Drafter LLM",
     "serving_endpoint":{"name":"databricks-claude-sonnet-4-6","permission":"CAN_QUERY"}},
    {"name":"summarizer-model","description":"Summarizer LLM",
     "serving_endpoint":{"name":"databricks-claude-haiku-4-5","permission":"CAN_QUERY"}},
    {"name":"embedding-model","description":"Embedding model",
     "serving_endpoint":{"name":"databricks-gte-large-en","permission":"CAN_QUERY"}}
  ]
}
EOF
databricks apps update rate-case-workbench --json @/tmp/app-res.json --profile=$PROFILE
```

**Grant UC permissions** (the app SP needs SELECT/MODIFY on the schemas to bootstrap tables):

```bash
for SCHEMA in rcw_app rcw_knowledge rcw_audit rcw_tabular; do
  for PRIV in "USE SCHEMA" "CREATE TABLE" "CREATE VOLUME" "SELECT" "MODIFY"; do
    databricks api post /api/2.0/sql/statements --profile=$PROFILE --json "{\"warehouse_id\":\"$WAREHOUSE_ID\",\"statement\":\"GRANT $PRIV ON SCHEMA $CATALOG.$SCHEMA TO \\\`$SP\\\`\",\"wait_timeout\":\"30s\"}" > /dev/null
  done
done
databricks api post /api/2.0/sql/statements --profile=$PROFILE --json "{\"warehouse_id\":\"$WAREHOUSE_ID\",\"statement\":\"GRANT USE CATALOG ON CATALOG $CATALOG TO \\\`$SP\\\`\",\"wait_timeout\":\"30s\"}"
databricks api post /api/2.0/sql/statements --profile=$PROFILE --json "{\"warehouse_id\":\"$WAREHOUSE_ID\",\"statement\":\"GRANT READ VOLUME, WRITE VOLUME ON VOLUME $CATALOG.rcw_knowledge.docs_raw TO \\\`$SP\\\`\",\"wait_timeout\":\"30s\"}"
```

---

## 6. Create the frontend build job and run it (one-time)

The frontend is React/Vite and needs to be built into static files. We provide a Databricks Job that builds it on Databricks compute (no need for Node locally):

```bash
cat > /tmp/build-fe-job.json <<EOF
{
  "name": "rcw-build-frontend",
  "tasks": [{
    "task_key": "build_frontend",
    "spark_python_task": {"python_file": "$WORKSPACE_PATH/jobs/build_frontend.py"},
    "environment_key": "default",
    "timeout_seconds": 1800
  }],
  "environments": [{
    "environment_key": "default",
    "spec": {"client": "1", "dependencies": []}
  }]
}
EOF
BUILD_JOB_ID=$(databricks jobs create --json @/tmp/build-fe-job.json --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
echo "Build job: $BUILD_JOB_ID"

databricks jobs run-now $BUILD_JOB_ID --profile=$PROFILE
```

Wait for it to complete (~5-7 min). You can watch with:
```bash
databricks jobs list-runs --job-id $BUILD_JOB_ID --limit 1 --profile=$PROFILE
```

When result_state is `SUCCESS`, the frontend `dist/` will be written back to the workspace path.

---

## 7. First app deploy

```bash
databricks apps deploy rate-case-workbench \
  --source-code-path "$WORKSPACE_PATH" \
  --profile=$PROFILE
```

This:
- Installs Python deps from `requirements.txt`
- Starts the FastAPI server
- On first startup, runs the **schema bootstrap**: creates the `rcw` Postgres schema, all 25+ tables, applies enum values, sets DB defaults, and seeds the 6 baseline roles

Watch the logs:
```bash
databricks apps logs rate-case-workbench --tail-lines 20 --profile=$PROFILE
```

You should see:
```
Schema bootstrap complete (schema=rcw)
Application startup complete.
```

**Open the app:** the URL is in `databricks apps get rate-case-workbench` (`url` field). Sign in via Databricks SSO. You'll auto-get admin role if your email is in `RCW_ADMIN_EMAILS`.

---

## 8. Bootstrap Vector Search indices

```bash
cat > /tmp/vs-job.json <<EOF
{
  "name": "rcw-bootstrap-vector-search",
  "tasks": [{
    "task_key": "bootstrap_vs",
    "spark_python_task": {"python_file": "$WORKSPACE_PATH/jobs/bootstrap_vector_search.py"},
    "environment_key": "default",
    "timeout_seconds": 1800
  }],
  "environments": [{
    "environment_key": "default",
    "spec": {"client": "1", "dependencies": ["databricks-sdk>=0.40.0", "databricks-vectorsearch>=0.40"]}
  }]
}
EOF
VS_JOB_ID=$(databricks jobs create --json @/tmp/vs-job.json --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
databricks jobs run-now $VS_JOB_ID --profile=$PROFILE
```

This creates the 3 Delta source tables (chunks, prior_responses) and the 3 Vector Search indices that the agent uses for retrieval.

> **You can skip this in Path B (your own data)** and run it later after you've uploaded enough documents to make retrieval useful.

---

## 9A. Path A — With synthetic data (NLPG demo)

This generates ~30 LLM-authored utility documents, ~115 DRs, 40 prior responses, plus testimony/briefs/orders across 6 cases at every lifecycle stage. Uses Claude Sonnet 4.6 — expect ~$5-10 in inference cost.

```bash
cat > /tmp/seed-job.json <<EOF
{
  "name": "rcw-seed-nlpg",
  "tasks": [
    {"task_key": "generate_docs", "spark_python_task": {"python_file": "$WORKSPACE_PATH/seed/generate.py"}, "environment_key": "default", "timeout_seconds": 5400},
    {"task_key": "seed_db", "depends_on": [{"task_key": "generate_docs"}], "spark_python_task": {"python_file": "$WORKSPACE_PATH/seed/seed_db.py"}, "environment_key": "default", "timeout_seconds": 1800},
    {"task_key": "setup_genie", "depends_on": [{"task_key": "seed_db"}], "spark_python_task": {"python_file": "$WORKSPACE_PATH/seed/setup_genie_space.py"}, "environment_key": "default", "timeout_seconds": 1200}
  ],
  "environments": [{
    "environment_key": "default",
    "spec": {"client": "1", "dependencies": [
      "databricks-sdk>=0.40.0","openai>=1.52.0","pydantic>=2.7.0",
      "sqlalchemy[asyncio]>=2.0.30","asyncpg>=0.29.0","httpx>=0.27.0","nest_asyncio>=1.6.0"
    ]}
  }]
}
EOF
SEED_JOB_ID=$(databricks jobs create --json @/tmp/seed-job.json --profile=$PROFILE --output json | python3 -c "import json,sys; print(json.load(sys.stdin)['job_id'])")
databricks jobs run-now $SEED_JOB_ID --profile=$PROFILE
```

When this finishes (60-90 min — generate is the slow part), refresh the app and you'll see the full NLPG dataset. **You're done.** Skip to step 10.

---

## 9B. Path B — Use your own data (skip synthetic)

Skip the seed job entirely. Instead, build your case from the UI:

1. Open the app → top header → **Admin** → **Cases** → **Create case**.
   Fill in: name, docket number, jurisdiction, commission, utility name. The 10 standard phases are auto-created.
2. **Add witnesses** → Side nav → **Witnesses** → **Add witness** for each in-house or external witness, with their expertise areas.
3. **Upload documents** → Side nav → **Knowledge** → **Upload document**. Each upload:
   - Lands in `/Volumes/<catalog>/rcw_knowledge/docs_raw/<case_id>/`
   - Triggers the ingest job (chunk + embed) → searchable in Vector Search
   - Appears in the Knowledge Library with classification badges (public / confidential / privileged)
4. **Ingest data requests** — three options:
   - **Manual**: Side nav → **Discovery** → **Manual DR** button (top right)
   - **Webhook**: `POST $APP_URL/api/v1/webhook/data-request` from your portal/email parser with `{docket_number, dr_number, requester, requester_kind, subject, body, priority?, issued_date?, due_date?}`
   - **Bulk import**: write to the `data_requests` table in Lakebase directly (e.g. via a Databricks notebook using the same connection pattern in `seed/seed_db.py`)
5. **Log intervenor positions** — Side nav → **Rebuttal** → **Log position** for each opposing position you want to track and rebut.
6. **Set up Genie** (optional, for tabular evidence Q&A):
   - Create a Genie space in the Databricks UI over whatever tabular evidence tables you want to expose (rate base, capex plan, customer counts, etc.)
   - Copy the space ID
   - In the app: **Admin → Genie → Register room** with that space ID

Everything else (workflow, drafter, checklist, rebuttal, briefs, hearings, compliance, automation rules, agent memory, audit log) works on your own data with no further setup.

---

## 10. Verify it's working

Quick smoke tests:

| What to try | Expected |
|---|---|
| Open the URL → SSO login | Lands on Cases landing page |
| Top header **Portfolio** button | Shows portfolio dashboard (empty for Path B, populated for Path A) |
| Side nav → **Knowledge** → click any document (Path A) | Modal viewer opens with the file content from UC Volume |
| Side nav → **Discovery** → click a DR → **Draft with agent** (Path A) or upload your own DR (Path B) | Agent retrieves evidence + writes a draft |
| Same screen → **Checklist** tab → **Run evaluation** | Returns pass/needs_attention/fail per item with suggested addenda |
| Bottom-right green ✨ **Sparky** button | Chat opens, can answer app questions + case doc questions |
| **Admin → Automation → Run all rules now** | Evaluates rules; logs to audit |

If anything 500s, check:
```bash
databricks apps logs rate-case-workbench --tail-lines 60 --profile=$PROFILE
```

Most common issues:
- **403 on `/serving-endpoints/...`** → re-run step 5's resource binding (FM endpoint not bound to app SP)
- **"relation does not exist"** → the app didn't finish bootstrap; redeploy
- **Frontend doesn't render** → re-run the build job (step 6) then redeploy the app

---

## 11. Iterating on the code

Local edit → workspace sync → app redeploy:

```bash
# Edit a backend file in your local checkout, then:
databricks sync . "$WORKSPACE_PATH" --exclude node_modules --exclude .venv --exclude __pycache__ --exclude .git --profile=$PROFILE
databricks apps deploy rate-case-workbench --source-code-path "$WORKSPACE_PATH" --profile=$PROFILE
```

For frontend changes: same sync + re-run the build job + redeploy the app.

---

## 12. Cleanup (when you're done)

```bash
databricks apps delete rate-case-workbench --profile=$PROFILE
databricks database delete-database-instance rcw-lakebase --profile=$PROFILE
databricks vector-search-endpoints delete-endpoint rcw-vs --profile=$PROFILE
# UC schemas + Volume + tables can stay or be dropped via SQL
```

---

## Architecture cheatsheet

```
[ Databricks App ] (FastAPI + React/Vite SPA, deployed via `databricks apps deploy`)
       │
       ├─► Lakebase Postgres (rcw-lakebase) — all OLTP workflow state
       ├─► Unity Catalog
       │     ├─ rcw_knowledge.documents + chunks  (Delta, sync'd to Vector Search)
       │     ├─ rcw_knowledge.docs_raw            (Volume, raw uploads)
       │     ├─ rcw_audit.*                       (Delta, CDC mirror of events)
       │     └─ rcw_tabular.*                     (Delta, Genie evidence)
       ├─► Vector Search endpoint (rcw-vs)
       │     ├─ chunks_case_idx
       │     ├─ chunks_jurisdiction_idx
       │     └─ prior_responses_idx
       ├─► Foundation Model API
       │     ├─ databricks-claude-sonnet-4-6   (drafter / checklist / position-checker)
       │     ├─ databricks-claude-haiku-4-5    (summarizer / redactor)
       │     └─ databricks-gte-large-en        (embeddings)
       └─► Genie space — natural-language SQL over rcw_tabular.*
```

---

## Files of interest

| Path | What it is |
|---|---|
| `app.yaml` | Databricks App manifest — env vars + entry command |
| `backend/app.py` | FastAPI factory + on-startup schema bootstrap |
| `backend/models.py` | SQLAlchemy ORM models (the canonical Lakebase schema) |
| `backend/routers/*.py` | 30+ REST endpoints (one router per domain area) |
| `backend/services/*.py` | LLM, Vector Search, Genie, audit, ingest helpers |
| `frontend/src/routes/*.tsx` | React routes (Cases, Drafter, Testimony, Rebuttal, Portfolio, …) |
| `jobs/*.py` | Databricks Jobs: frontend build, document ingest, VS bootstrap |
| `seed/*.py` | Synthetic NLPG dataset generators |
| `requirements.txt` | Python dependencies |

For questions, the in-app **Sparky** chatbot can answer most "how do I…" questions about the workbench itself.
