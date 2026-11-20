import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

from agent_core.loop import run_triage
from mcp_servers.telemetry_server.db_inspector import get_db_health
from mcp_servers.telemetry_server.executor import terminate_backend_pid


def _find_ground_truth_blocker_pid() -> int | None:
    health = get_db_health()
    for sess in health.get("active_sessions", []):
        if sess.get("state") == "idle in transaction" and "FOR UPDATE" in (sess.get("query") or ""):
            return sess["pid"]
    return None


async def eval_db_lock_scenario() -> dict:
    chaos_proc = subprocess.Popen([sys.executable, "testbed/chaos/inject_db_lock.py"])
    start = time.perf_counter()

    try:
        # Wait for lock + initial failed requests to populate logs
        await asyncio.sleep(5)
        ground_truth_pid = _find_ground_truth_blocker_pid()

        alert = {
            "alert_name": "HighOrderFailureRate",
            "service": "target-api",
            "symptom": "POST /orders returning 500 errors and lock timeout exceptions",
        }
        report = await run_triage(alert)
        latency_sec = round(time.perf_counter() - start, 2)

        predicted_pid = report.proposed_action.target_pid
        rc_lower = report.root_cause.lower()
        root_cause_hit = ("lock" in rc_lower) and ("sku-00001" in rc_lower or "inventory" in rc_lower)
        action_hit = report.proposed_action.action_type == "terminate_pid"
        pid_exact_match = (ground_truth_pid is not None) and (predicted_pid == ground_truth_pid)

        score = sum([root_cause_hit, action_hit, pid_exact_match]) / 3.0

        return {
            "scenario": "postgres_row_lock_contention",
            "passed": score == 1.0,
            "score": round(score, 2),
            "latency_sec": latency_sec,
            "ground_truth_pid": ground_truth_pid,
            "predicted_pid": predicted_pid,
            "checks": {
                "root_cause_identified": root_cause_hit,
                "correct_action_type": action_hit,
                "exact_blocker_pid_match": pid_exact_match,
            },
            "report": report.model_dump(),
        }
    finally:
        chaos_proc.terminate()
        chaos_proc.wait(timeout=5)
        # Clean up any leftover lock session so testbed stays healthy
        leftover_pid = _find_ground_truth_blocker_pid()
        if leftover_pid:
            terminate_backend_pid(leftover_pid)


async def main() -> None:
    result = await eval_db_lock_scenario()
    report_path = Path(f"evals/reports/eval_{int(time.time())}.json")
    report_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("\n=== CHAOS EVAL SUMMARY ===")
    print(json.dumps({k: v for k, v in result.items() if k != "report"}, indent=2))
    print(f"\nSaved full report to {report_path}")


if __name__ == "__main__":
    asyncio.run(main())