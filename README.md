# sentinel-sre

Autonomous Site Reliability Engineering (SRE) triage agent built from first principles—combining a custom Model Context Protocol (MCP) telemetry server, isolated E2B Firecracker sandboxes for log analysis, and a raw Python control loop powered by Gemini.

## Architecture

```text
[Alert Payload]
       │
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
                │ read-only SQL     └───────────────────────┘
                ▼
┌───────────────────────────────┐
│  Target Testbed (testbed/)    │
│  • FastAPI + PostgreSQL 16    │
│  • Reproducible chaos scripts │
└───────────────────────────────┘
*Gated behind Human-in-the-Loop (HITL) approval.
```

## Prerequisites

- **Python 3.12+** & [`uv`](https://docs.astral.sh/uv/)
- **Docker Desktop** (Linux containers)
- **API Keys:** `GEMINI_API_KEY` and `E2B_API_KEY`

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

### 3. Run an End-to-End Chaos Triage

**Terminal 1 — Inject a database row-lock bottleneck:**

```bash
uv run python testbed/chaos/inject_db_lock.py
```

**Terminal 2 — Trigger the autonomous triage agent (3–5 seconds later):**

```bash
uv run python -m agent_core.loop
```

The agent inspects live PostgreSQL lock waits via MCP, streams application logs into an isolated E2B sandbox, runs diagnostic Python analysis, and outputs a validated `IncidentReport` JSON identifying the blocking PID and proposed remediation.

## Standalone MCP Inspector

To test the telemetry MCP server tools interactively without the LLM loop:

```bash
uv run mcp dev src/mcp_servers/telemetry_server/server.py
```

## Project Layout

```text
sentinel-sre/
├── src/
│   ├── agent_core/                 # Raw Gemini control loop, E2B wrapper, Pydantic schemas
│   └── mcp_servers/
│       └── telemetry_server/       # Custom MCP 2.x server (DB health, log streaming, PID exec)
├── testbed/                        # Target FastAPI + Postgres stack & chaos scripts
├── pyproject.toml
└── README.md
```