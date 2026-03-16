from datetime import datetime
from typing import List
from pydantic import BaseModel, field_validator
from app.schemas.scan import ScanResponse


class CreateRepoRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        v = v.rstrip("/").rstrip(".git")
        if not (v.startswith("https://github.com/") or v.startswith("https://gitlab.com/")):
            raise ValueError("URL must start with https://github.com/ or https://gitlab.com/")
        parts = v.split("/")
        if len(parts) < 5:
            raise ValueError("URL must include owner and repository name")
        return v


class RepoResponse(BaseModel):
    id: str
    url: str
    name: str
    scan_count: int = 0
    created_at: datetime
    updated_at: datetime


class RepoDetailResponse(BaseModel):
    id: str
    url: str
    name: str
    scan_count: int = 0
    scans: List[ScanResponse] = []
    created_at: datetime
    updated_at: datetime
