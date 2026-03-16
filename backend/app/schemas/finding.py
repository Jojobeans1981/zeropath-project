from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class FindingResponse(BaseModel):
    id: str
    scan_id: str
    identity_hash: str
    severity: str
    vulnerability_type: str
    file_path: str
    line_number: int
    code_snippet: str
    description: str
    explanation: str
    triage_status: Optional[str] = None
    triage_notes: Optional[str] = None
    created_at: datetime


class TriageRequest(BaseModel):
    status: str
    notes: Optional[str] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in {"open", "false_positive", "resolved"}:
            raise ValueError("Status must be one of: open, false_positive, resolved")
        return v
