import json
import os
import time
from pathlib import Path
from e2b_code_interpreter import Sandbox

REPO_ROOT = Path(__file__).resolve().parents[3]


def stream_logs_to_sandbox(sandbox_id: str, minutes: int = 15, level_filter: str | None = None) -> dict:
    raw_path = os.getenv("TARGET_LOG_PATH", "testbed/logs/app.jsonl")
    log_path = Path(raw_path) if Path(raw_path).is_absolute() else (REPO_ROOT / raw_path)

    if not log_path.exists():
        return {"error": f"Log file not found at {log_path}."}

    cutoff = time.time() - (minutes * 60)
    matched_lines: list[str] = []
    error_count = 0

    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("ts", 0) < cutoff:
                continue
            lvl = entry.get("level", "")
            if level_filter and lvl.upper() != level_filter.upper():
                continue
            if lvl.upper() == "ERROR":
                error_count += 1
            matched_lines.append(line)

    remote_path = "/home/user/logs.jsonl"
    payload = "\n".join(matched_lines) if matched_lines else ""

    sbx = Sandbox.connect(sandbox_id)
    sbx.files.write(remote_path, payload)

    return {
        "sandbox_id": sandbox_id,
        "remote_path": remote_path,
        "total_lines": len(matched_lines),
        "error_count": error_count,
        "sample_schema": ["ts", "level", "event", "sku", "latency_ms", "error"],
        "instruction": f"Use run_diagnostic_python to analyze {remote_path} via json or pandas.",
    }