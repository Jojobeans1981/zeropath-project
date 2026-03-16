from typing import Optional, List, Tuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.finding import Finding
from app.models.scan import Scan
from app.models.repository import Repository
from app.models.triage import TriageStatus

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


async def get_findings_for_scan(
    db: AsyncSession,
    scan_id: str,
    user_id: str,
    severity_filter: Optional[str] = None,
) -> List[Tuple[Finding, Optional[TriageStatus]]]:
    # Verify scan belongs to user
    result = await db.execute(
        select(Scan).options(selectinload(Scan.repo)).where(Scan.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found."}})
    if scan.repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    stmt = (
        select(Finding, TriageStatus)
        .outerjoin(
            TriageStatus,
            (TriageStatus.finding_id == Finding.id) & (TriageStatus.user_id == user_id),
        )
        .where(Finding.scan_id == scan_id)
    )

    if severity_filter:
        severities = [s.strip().lower() for s in severity_filter.split(",")]
        stmt = stmt.where(Finding.severity.in_(severities))

    result = await db.execute(stmt)
    rows = result.all()

    # Sort by severity priority
    rows_sorted = sorted(rows, key=lambda r: SEVERITY_ORDER.get(r[0].severity, 5))
    return rows_sorted


async def get_finding(db: AsyncSession, finding_id: str, user_id: str) -> Finding:
    result = await db.execute(
        select(Finding)
        .options(selectinload(Finding.scan).selectinload(Scan.repo))
        .where(Finding.id == finding_id)
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Finding not found."}})
    if finding.scan.repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})
    return finding


async def get_finding_with_triage(
    db: AsyncSession, finding_id: str, user_id: str
) -> Tuple[Finding, Optional[TriageStatus]]:
    finding = await get_finding(db, finding_id, user_id)

    result = await db.execute(
        select(TriageStatus).where(
            TriageStatus.finding_id == finding_id,
            TriageStatus.user_id == user_id,
        )
    )
    triage = result.scalar_one_or_none()
    return finding, triage


async def update_triage(
    db: AsyncSession,
    finding_id: str,
    user_id: str,
    status: str,
    notes: Optional[str] = None,
) -> TriageStatus:
    # Verify finding exists and user owns the repo
    await get_finding(db, finding_id, user_id)

    # Upsert triage status
    result = await db.execute(
        select(TriageStatus).where(
            TriageStatus.finding_id == finding_id,
            TriageStatus.user_id == user_id,
        )
    )
    triage = result.scalar_one_or_none()

    if triage:
        triage.status = status
        triage.notes = notes
    else:
        triage = TriageStatus(
            finding_id=finding_id,
            user_id=user_id,
            status=status,
            notes=notes,
        )
        db.add(triage)

    await db.commit()
    await db.refresh(triage)
    return triage


async def compare_scans(
    db: AsyncSession,
    base_scan_id: str,
    head_scan_id: str,
    user_id: str,
) -> dict:
    """Compare two scans and categorize findings as new, fixed, or persisting."""
    # Fetch both scans with repo loaded
    base_result = await db.execute(
        select(Scan).options(selectinload(Scan.repo)).where(Scan.id == base_scan_id)
    )
    base_scan = base_result.scalar_one_or_none()
    head_result = await db.execute(
        select(Scan).options(selectinload(Scan.repo)).where(Scan.id == head_scan_id)
    )
    head_scan = head_result.scalar_one_or_none()

    if not base_scan or not head_scan:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found."}})

    if base_scan.repo_id != head_scan.repo_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "DIFFERENT_REPOS", "message": "Cannot compare scans from different repositories."}})

    if base_scan.status != "complete" or head_scan.status != "complete":
        raise HTTPException(status_code=400, detail={"error": {"code": "SCAN_NOT_COMPLETE", "message": "Both scans must be complete to compare."}})

    if base_scan.repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    # Get findings for both scans
    base_findings_result = await db.execute(select(Finding).where(Finding.scan_id == base_scan_id))
    base_findings = {f.identity_hash: f for f in base_findings_result.scalars().all()}

    head_findings_result = await db.execute(select(Finding).where(Finding.scan_id == head_scan_id))
    head_findings = {f.identity_hash: f for f in head_findings_result.scalars().all()}

    # Compute sets
    base_hashes = set(base_findings.keys())
    head_hashes = set(head_findings.keys())

    new_hashes = head_hashes - base_hashes
    fixed_hashes = base_hashes - head_hashes
    persisting_hashes = base_hashes & head_hashes

    # Helper to convert finding to response dict with triage
    async def finding_to_response(finding: Finding) -> dict:
        triage_result = await db.execute(
            select(TriageStatus).where(
                TriageStatus.finding_id == finding.id,
                TriageStatus.user_id == user_id,
            )
        )
        triage = triage_result.scalar_one_or_none()
        return {
            "id": finding.id,
            "scan_id": finding.scan_id,
            "identity_hash": finding.identity_hash,
            "severity": finding.severity,
            "vulnerability_type": finding.vulnerability_type,
            "file_path": finding.file_path,
            "line_number": finding.line_number,
            "code_snippet": finding.code_snippet,
            "description": finding.description,
            "explanation": finding.explanation,
            "created_at": finding.created_at,
            "triage_status": triage.status if triage else None,
            "triage_notes": triage.notes if triage else None,
        }

    new_list = [await finding_to_response(head_findings[h]) for h in new_hashes]
    fixed_list = [await finding_to_response(base_findings[h]) for h in fixed_hashes]
    persisting_list = [await finding_to_response(head_findings[h]) for h in persisting_hashes]

    return {
        "base_scan_id": base_scan_id,
        "head_scan_id": head_scan_id,
        "counts": {"new": len(new_list), "fixed": len(fixed_list), "persisting": len(persisting_list)},
        "new": new_list,
        "fixed": fixed_list,
        "persisting": persisting_list,
    }


def carry_forward_triage(sync_db, scan_id: str) -> int:
    """Copy triage statuses from previous scan's findings to current scan's findings with matching identity_hash.
    Uses synchronous DB session (called from Celery worker).
    Returns count of carried-forward statuses."""
    current_scan = sync_db.query(Scan).filter(Scan.id == scan_id).first()
    if not current_scan:
        return 0

    # Find previous completed scan for same repo
    previous_scan = (
        sync_db.query(Scan)
        .filter(
            Scan.repo_id == current_scan.repo_id,
            Scan.id != scan_id,
            Scan.status == "complete",
        )
        .order_by(Scan.created_at.desc())
        .first()
    )
    if not previous_scan:
        return 0

    # Get current scan's findings
    current_findings = sync_db.query(Finding).filter(Finding.scan_id == scan_id).all()
    current_hash_map = {f.identity_hash: f for f in current_findings}

    # Get previous scan's findings with triage
    prev_findings = sync_db.query(Finding).filter(Finding.scan_id == previous_scan.id).all()

    carried = 0
    for prev_finding in prev_findings:
        if prev_finding.identity_hash not in current_hash_map:
            continue

        current_finding = current_hash_map[prev_finding.identity_hash]

        # Get triage records for previous finding
        triage_records = (
            sync_db.query(TriageStatus)
            .filter(TriageStatus.finding_id == prev_finding.id)
            .all()
        )

        for triage in triage_records:
            new_triage = TriageStatus(
                finding_id=current_finding.id,
                user_id=triage.user_id,
                status=triage.status,
                notes=triage.notes,
            )
            sync_db.add(new_triage)
            carried += 1

    sync_db.commit()
    return carried
