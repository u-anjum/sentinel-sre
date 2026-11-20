# sentinel-sre

Autonomous Site Reliability Engineering (SRE) triage and remediation agent built from first principles—combining a custom Model Context Protocol (MCP) telemetry server, isolated E2B Firecracker sandboxes for log analysis, a raw Python control loop powered by Gemini, and a FastAPI Human-in-the-Loop (HITL) control plane.

## Architecture

```
[Monitoring / Alertmanager]
            │ POST /webhooks/alert
            ▼
┌───────────────────────────────────────────────────────────┐
│  Control Plane API (src/api) & SQLite Store (src/db)      │
│  • Persists incident lifecycle (TRIAGING → AWAITING_APPROVAL)│
│  • Gates destructive remediation behind /approve          │
└───────────────────────────┬───────────────────────────────┘
                            │ async background triage
                            ▼
┌───────────────────────────────────────────────────────────┐
│  Agent Core (src/agent_core)                              │
│  • Pure-Python async control loop (Gemini + Pydantic v2)  │
│  • Enforces read-only triage & structured IncidentReport  │
└───────────────┬───────────────────────────┬───────────────┘
                │ stdio (MCP 2.x)           │ HTTPS
                ▼                           ▼
┌───────────────────────────────┐   ┌───────────────────────┐
│  Telemetry MCP Server         │   │  E2B MicroVM Sandbox  │
│  (src/mcp_servers)            │   │  (/home/user)         │
│  • inspect_db_health          │   │  • Receives streamed  │
│  • fetch_logs_to_sandbox ─────┼──▶│    logs.jsonl         │
│  • execute_terminate_pid*     │   │  • Runs diagnostic    │
└───────────────┬───────────────┘   │    Python scripts     │
                │ SQL               └───────────────────────┘
                ▼
┌───────────────────────────────┐
│  Target Testbed (testbed/)    │
│  • FastAPI + PostgreSQL 16    │
│  • Reproducible chaos scripts │
└───────────────────────────────┘
*Executed only after explicit human sign-off via /incidents/{id}/approve.
```

## Prerequisites

* **Python 3.12+** & [`uv`](https://docs.astral.sh/uv/)
* **Docker Desktop** (Linux containers)
* **API Keys:** `GEMINI_API_KEY` and `E2B_API_KEY`

## Quickstart

### 1. Install Dependencies & Configure Environment

```bash
uv sync
cp .env.example .env
```

Edit `.env` and add your `GEMINI_API_KEY` and `E2B_API_KEY`.

### 2. Start the Target Testbed

```bash
cd testbed
docker compose up -d --build
cd ..
```

See [`testbed/README.md`](testbed/README.md) for testbed endpoints and teardown commands.

### 3. Run the Control Plane & HITL Workflow

**Terminal 1 — Start the FastAPI Control Plane:**

```bash
uv run uvicorn api.main:app --port 8000
```

**Terminal 2 — Inject a database row-lock bottleneck:**

```bash
uv run python testbed/chaos/inject_db_lock.py
```

**Terminal 3 — Trigger an alert webhook, inspect triage, and approve remediation:**

```bash
# 1. Trigger alert webhook
curl -X POST "http://localhost:8000/webhooks/alert" \
  -H "Content-Type: application/json" \
  -d '{"alert_name":"HighOrderFailureRate","service":"target-api","symptom":"POST /orders returning 500 errors"}'

# 2. Inspect structured IncidentReport (replace <incident_id>)
curl "http://localhost:8000/incidents/<incident_id>"

# 3. Approve remediation (terminates blocking Postgres PID via MCP)
curl -X POST "http://localhost:8000/incidents/<incident_id>/approve" \
  -H "Content-Type: application/json" \
  -d '{"approved":true,"operator":"oncall-engineer","comment":"Verified blocker PID"}'
```

## Automated Chaos Eval Suite

Run the end-to-end evaluation harness to inject live faults, benchmark root-cause accuracy and exact PID precision, and write a JSON report to `evals/reports/`:

```bash
uv run python evals/run_evals.py
```

## Standalone CLI & MCP Inspector

* **Run the triage loop directly without FastAPI:**
  ```bash
  uv run python -m agent_core.loop
  ```
* **Inspect MCP telemetry tools interactively:**
  ```bash
  uv run mcp dev src/mcp_servers/telemetry_server/server.py
  ```

## Project Layout

```
sentinel-sre/
├── src/
│   ├── agent_core/                 # Raw Gemini control loop, E2B wrapper, Pydantic schemas
│   ├── api/                        # FastAPI webhook receiver & HITL approval endpoints
│   ├── db/                         # SQLite incident state & audit persistence
│   └── mcp_servers/
│       └── telemetry_server/       # Custom MCP 2.x server (DB health, log streaming, PID exec)
├── evals/                          # Automated chaos evaluation harness & reports
├── testbed/                        # Target FastAPI + Postgres stack & chaos scripts
├── pyproject.toml
└── README.md
```