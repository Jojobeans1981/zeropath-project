from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
from app.schemas.finding import FindingResponse


class CreateScanRequest(BaseModel):
    repo_id: str


class ScanResponse(BaseModel):
    id: str
    repo_id: str
    status: str
    commit_sha: Optional[str] = None
    error_message: Optional[str] = None
    files_scanned: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime


class ComparisonCounts(BaseModel):
    new: int
    fixed: int
    persisting: int


class ComparisonResponse(BaseModel):
    base_scan_id: str
    head_scan_id: str
    counts: ComparisonCounts
    new: List[FindingResponse]
    fixed: List[FindingResponse]
    persisting: List[FindingResponse]
