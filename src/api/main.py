import os
import sys
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from pydantic import BaseModel

from agent_core.loop import run_triage
from db.store import create_incident, get_incident, init_db, list_incidents, update_incident


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Sentinel-SRE Control Plane", lifespan=lifespan)


class AlertWebhook(BaseModel):
    alert_name: str
    service: str
    symptom: str


class ApprovalDecision(BaseModel):
    approved: bool
    operator: str = "oncall-engineer"
    comment: str | None = None


async def _background_triage(incident_id: str, alert_payload: dict) -> None:
    try:
        report = await run_triage(alert_payload)
        report_dict = report.model_dump()
        next_status = (
            "AWAITING_APPROVAL"
            if report.proposed_action.action_type == "terminate_pid" and report.proposed_action.target_pid
            else "RESOLVED"
        )
        update_incident(incident_id, status=next_status, report=report_dict)
    except Exception as exc:
        update_incident(incident_id, status="FAILED", error_msg=str(exc))


async def _execute_mcp_remediation(pid: int) -> dict:
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["src/mcp_servers/telemetry_server/server.py"],
        env=os.environ.copy(),
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            mcp_res = await session.call_tool("execute_terminate_pid", arguments={"pid": pid})
            return {"output": [c.text for c in mcp_res.content if hasattr(c, "text")]}


@app.post("/webhooks/alert", status_code=202)
async def receive_alert(alert: AlertWebhook, background_tasks: BackgroundTasks):
    payload = alert.model_dump()
    incident_id = create_incident(payload)
    background_tasks.add_task(_background_triage, incident_id, payload)
    return {"incident_id": incident_id, "status": "TRIAGING"}


@app.get("/incidents")
def get_all_incidents():
    return {"incidents": list_incidents()}


@app.get("/incidents/{incident_id}")
def get_incident_detail(incident_id: str):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    return inc


@app.post("/incidents/{incident_id}/approve")
async def approve_remediation(incident_id: str, decision: ApprovalDecision):
    inc = get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if inc["status"] != "AWAITING_APPROVAL":
        raise HTTPException(status_code=409, detail=f"Incident is in state '{inc['status']}', not AWAITING_APPROVAL")

    if not decision.approved:
        exec_record = {"approved": False, "operator": decision.operator, "comment": decision.comment}
        update_incident(incident_id, status="REJECTED", execution=exec_record)
        return {"incident_id": incident_id, "status": "REJECTED", "execution": exec_record}

    target_pid = inc["report"]["proposed_action"]["target_pid"]
    mcp_result = await _execute_mcp_remediation(pid=target_pid)
    exec_record = {
        "approved": True,
        "operator": decision.operator,
        "comment": decision.comment,
        "terminated_pid": target_pid,
        "mcp_result": mcp_result,
    }
    update_incident(incident_id, status="RESOLVED", execution=exec_record)
    return {"incident_id": incident_id, "status": "RESOLVED", "execution": exec_record}