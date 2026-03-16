from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.finding import FindingResponse, TriageRequest
from app.services import finding_service

router = APIRouter(prefix="/api/findings", tags=["findings"])


@router.get("/{finding_id}")
async def get_finding(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    finding, triage = await finding_service.get_finding_with_triage(db, finding_id, current_user.id)
    data = FindingResponse(
        id=finding.id,
        scan_id=finding.scan_id,
        identity_hash=finding.identity_hash,
        severity=finding.severity,
        vulnerability_type=finding.vulnerability_type,
        file_path=finding.file_path,
        line_number=finding.line_number,
        code_snippet=finding.code_snippet,
        description=finding.description,
        explanation=finding.explanation,
        triage_status=triage.status if triage else None,
        triage_notes=triage.notes if triage else None,
        created_at=finding.created_at,
    )
    return {"success": True, "data": data.model_dump()}


@router.patch("/{finding_id}/triage")
async def triage_finding(
    finding_id: str,
    req: TriageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    triage = await finding_service.update_triage(
        db, finding_id, current_user.id, req.status, req.notes
    )
    return {
        "success": True,
        "data": {
            "status": triage.status,
            "notes": triage.notes,
            "updated_at": triage.updated_at.isoformat() if triage.updated_at else None,
        },
    }
