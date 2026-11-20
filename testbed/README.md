# Target Testbed & Chaos Harness

Isolated target environment simulating a FastAPI + PostgreSQL service with reproducible production bottlenecks.

## Prerequisites
- Docker Desktop (Linux containers)
- Python 3.12+ & [`uv`](https://docs.astral.sh/uv/)

## Setup & Start

```bash
cd testbed
docker compose up -d --build
```

Verify health & schema:

```bash
curl -X POST "http://localhost:8001/orders?sku=SKU-00001&qty=1"
```

## Trigger Chaos Scenarios

From the repository root:

```bash
uv run python testbed/chaos/inject_db_lock.py
```

Structured application logs stream to `testbed/logs/app.jsonl`.

## Teardown

```bash
cd testbed
docker compose down -v
```