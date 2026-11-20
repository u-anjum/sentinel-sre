from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp_servers.telemetry_server.db_inspector import get_db_health
from mcp_servers.telemetry_server.log_fetcher import stream_logs_to_sandbox
from mcp_servers.telemetry_server.executor import terminate_backend_pid

load_dotenv()

mcp = MCPServer("sentinel-telemetry")

@mcp.tool()
def inspect_db_health() -> dict:
    """Inspect active PostgreSQL sessions, blocking PIDs, lock waits, and connection pool saturation."""
    return get_db_health()

@mcp.tool()
def fetch_logs_to_sandbox(sandbox_id: str, minutes: int = 15, level_filter: str | None = None) -> dict:
    """Stream recent application JSONL logs directly into an active E2B sandbox at /workspace/logs.jsonl.
    Returns only metadata counts so raw logs do not bloat the context window."""
    return stream_logs_to_sandbox(sandbox_id=sandbox_id, minutes=minutes, level_filter=level_filter)

@mcp.tool()
def execute_terminate_pid(pid: int) -> dict:
    """Terminate a blocking PostgreSQL backend PID. ONLY invoke after explicit human-in-the-loop approval."""
    return terminate_backend_pid(pid=pid)

if __name__ == "__main__":
    mcp.run(transport="stdio")