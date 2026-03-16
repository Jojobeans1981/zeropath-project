from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.finding import FindingResponse, TriageRequest
from app.services import finding_service, remediation_service

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
    current_user: User = Depends(require_role(["admin", "member"])),
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


@router.post("/{finding_id}/remediation")
async def generate_remediation(
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    remediation = await remediation_service.get_or_generate_remediation(db, finding_id, current_user.id)
    return {
        "success": True,
        "data": {
            "id": remediation.id,
            "fixed_code": remediation.fixed_code,
            "explanation": remediation.explanation,
            "confidence": remediation.confidence,
            "created_at": remediation.created_at.isoformat(),
        },
    }


@router.get("/{finding_id}/remediation")
async def get_remediation(
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    remediation = await remediation_service.get_or_generate_remediation(db, finding_id, current_user.id)
    return {
        "success": True,
        "data": {
            "id": remediation.id,
            "fixed_code": remediation.fixed_code,
            "explanation": remediation.explanation,
            "confidence": remediation.confidence,
            "created_at": remediation.created_at.isoformat(),
        },
    }
