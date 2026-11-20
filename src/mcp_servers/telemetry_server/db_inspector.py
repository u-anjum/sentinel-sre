import os
import psycopg
from psycopg.rows import dict_row

def get_db_health() -> dict:
    db_url = os.environ["TARGET_DATABASE_URL"]
    with psycopg.connect(db_url, row_factory=dict_row, options="-c default_transaction_read_only=on") as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.pid,
                    a.state,
                    a.wait_event_type,
                    a.wait_event,
                    EXTRACT(EPOCH FROM (NOW() - a.query_start))::numeric(10, 2) as duration_sec,
                    pg_blocking_pids(a.pid) as blocked_by_pids,
                    LEFT(a.query, 300) AS query
                FROM pg_stat_activity a
                WHERE a.datname = current_database()
                    AND a.pid <> pg_backend_pid()
                    AND a.state <> 'idle'
                ORDER BY duration_sec DESC NULLS LAST;
            """)
            active_sessions = cur.fetchall()

            cur.execute("""
                SELECT
                    count(*) AS total_connections,
                    count(*) FILTER (WHERE state = 'active') AS active,
                    count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx,
                    count(*) FILTER (WHERE wait_event_type = 'Lock') AS waiting_on_lock
                FROM pg_stat_activity
                WHERE datname = current_database()
            """)

            pool_summary = cur.fetchone()

    return {
        "pool_summary": dict(pool_summary) if pool_summary else {},
        "active_sessions": [dict(r) for r in active_sessions],
    }