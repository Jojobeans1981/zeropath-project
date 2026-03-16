from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.user import User
from app.schemas.scan import CreateScanRequest, ScanResponse
from app.schemas.finding import FindingResponse
from app.services import scan_service, finding_service, sarif_service

router = APIRouter(prefix="/api/scans", tags=["scans"])


@router.post("/")
async def create_scan(
    req: CreateScanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "member"])),
):
    scan = await scan_service.create_scan(db, req.repo_id, current_user.id)
    data = ScanResponse(
        id=scan.id,
        repo_id=scan.repo_id,
        status=scan.status,
        commit_sha=scan.commit_sha,
        error_message=scan.error_message,
        files_scanned=scan.files_scanned,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        created_at=scan.created_at,
    )
    return {"success": True, "data": data.model_dump()}


@router.get("/compare")
async def compare_scans_endpoint(
    base: str,
    head: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await finding_service.compare_scans(db, base, head, current_user.id)
    return {"success": True, "data": result}


@router.get("/{scan_id}/sarif")
async def export_sarif(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await scan_service.get_scan(db, scan_id, current_user.id)
    if scan.status != "complete":
        raise HTTPException(status_code=400, detail={"error": {"code": "SCAN_NOT_COMPLETE", "message": "Scan must be complete to export SARIF."}})
    rows = await finding_service.get_findings_for_scan(db, scan_id, current_user.id)
    findings = [f for f, _t in rows]
    sarif = sarif_service.generate_sarif(scan, findings)
    return JSONResponse(
        content=sarif,
        headers={"Content-Disposition": f"attachment; filename=zeropath-scan-{scan_id}.sarif.json"},
    )


@router.get("/{scan_id}")
async def get_scan(
    scan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan = await scan_service.get_scan(db, scan_id, current_user.id)
    data = ScanResponse(
        id=scan.id,
        repo_id=scan.repo_id,
        status=scan.status,
        commit_sha=scan.commit_sha,
        error_message=scan.error_message,
        files_scanned=scan.files_scanned,
        started_at=scan.started_at,
        completed_at=scan.completed_at,
        created_at=scan.created_at,
    )
    return {"success": True, "data": data.model_dump()}


@router.get("/{scan_id}/findings")
async def get_scan_findings(
    scan_id: str,
    severity: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await finding_service.get_findings_for_scan(db, scan_id, current_user.id, severity)
    data = [
        FindingResponse(
            id=f.id,
            scan_id=f.scan_id,
            identity_hash=f.identity_hash,
            severity=f.severity,
            vulnerability_type=f.vulnerability_type,
            file_path=f.file_path,
            line_number=f.line_number,
            code_snippet=f.code_snippet,
            description=f.description,
            explanation=f.explanation,
            triage_status=t.status if t else None,
            triage_notes=t.notes if t else None,
            created_at=f.created_at,
        ).model_dump()
        for f, t in rows
    ]
    return {"success": True, "data": data}
