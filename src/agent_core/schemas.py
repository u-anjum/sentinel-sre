from typing import Literal
from pydantic import BaseModel, Field

class ProposedAction(BaseModel):
    action_type: Literal["terminate_pid", "none"]
    target_pid: int | None = Field(default=None, description="Postgres backend PID to terminate if action_type is terminate_pid")
    rationale: str

class IncidentReport(BaseModel):
    severity: Literal["P1", "P2", "P3"]
    root_cause: str
    affected_services: list[str]
    evidence: list[str]
    proposed_action: ProposedAction