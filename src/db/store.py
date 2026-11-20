import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Literal

DB_PATH = Path("sentinel_state.db")

IncidentStatus = Literal["TRIAGING", "AWAITING_APPROVAL", "RESOLVED", "REJECTED", "FAILED"]


def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                status TEXT NOT NULL,
                alert_json TEXT NOT NULL,
                report_json TEXT,
                execution_json TEXT,
                error_msg TEXT
            );
        """)


def create_incident(alert_payload: dict) -> str:
    init_db()
    incident_id = f"inc_{uuid.uuid4().hex[:10]}"
    now = time.time()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO incidents (id, created_at, updated_at, status, alert_json) VALUES (?, ?, ?, ?, ?)",
            (incident_id, now, now, "TRIAGING", json.dumps(alert_payload)),
        )
    return incident_id


def update_incident(
    incident_id: str,
    status: IncidentStatus,
    report: dict | None = None,
    execution: dict | None = None,
    error_msg: str | None = None,
) -> None:
    now = time.time()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE incidents
            SET updated_at = ?,
                status = ?,
                report_json = COALESCE(?, report_json),
                execution_json = COALESCE(?, execution_json),
                error_msg = COALESCE(?, error_msg)
            WHERE id = ?
            """,
            (
                now,
                status,
                json.dumps(report) if report is not None else None,
                json.dumps(execution) if execution is not None else None,
                error_msg,
                incident_id,
            ),
        )


def get_incident(incident_id: str) -> dict | None:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "alert": json.loads(row["alert_json"]),
            "report": json.loads(row["report_json"]) if row["report_json"] else None,
            "execution": json.loads(row["execution_json"]) if row["execution_json"] else None,
            "error_msg": row["error_msg"],
        }


def list_incidents(limit: int = 20) -> list[dict]:
    init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT id, created_at, updated_at, status FROM incidents ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]