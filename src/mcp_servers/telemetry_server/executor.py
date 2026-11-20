import os
import psycopg


def terminate_backend_pid(pid: int) -> dict:
    db_url = os.environ["TARGET_DATABASE_URL"]
    with psycopg.connect(db_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_terminate_backend(%s);", (pid,))
            row = cur.fetchone()
            terminated = bool(row[0]) if row else False

    return {
        "pid": pid,
        "terminated": terminated,
        "status": "terminated" if terminated else "pid_not_found_or_already_exited",
    }