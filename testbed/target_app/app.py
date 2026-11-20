import json 
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException
from psycopg_pool import ConnectionPool

Path("/logs").mkdir(parents=True, exist_ok=True)
logger = logging.getLogger("target_api")
logger.setLevel(logging.INFO)
fh = logging.FileHandler("/logs/app.jsonl")
fh.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(fh)

def log_event(level: str, event: str, **kwargs):
    logger.info(json.dumps({"ts": time.time(), "level": level, "event": event, **kwargs}))

pool: ConnectionPool | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global pool
    pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=2, max_size=10, timeout=5.0)
    yield
    pool.close()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/orders")
def create_order(sku: str = "SKU-00001", qty: int = 1):
    t0 = time.perf_counter()

    try: 
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL lock_timeout = '2s';")
                cur.execute("UPDATE inventory SET stock = stock - %s, updated_at = NOW() WHERE sku = %s RETURNING stock;", (qty, sku))
                row = cur.fetchone()

                if not row:
                    raise HTTPException(404, "SKU not found")

                cur.execute("INSERT INTO orders (sku, qty, status) VALUES(%s, %s, 'confirmed);", (sku, qty))
        ms = round((time.perf_counter() - t0) * 1000, 2)
        log_event("INFO", "order_created", sku=sku, latency_ms = ms)
        return {"sku": sku, "remaining_stock": row[0], "latency_ms": ms}
    except Exception as e:
        ms = round((time.perf_counter() - t0) * 1000, 2)
        log_event("ERROR", "order_failed", sku=sku, latency_ms=ms, error=str(e))
        raise HTTPException(500, str(e))