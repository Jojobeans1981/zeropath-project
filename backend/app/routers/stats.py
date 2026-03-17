"""Analytics and statistics endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.finding import Finding
from app.models.triage import TriageStatus

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/dashboard")
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get dashboard statistics for the current user."""
    # Total repos
    repo_count = await db.execute(
        select(func.count(Repository.id)).where(Repository.user_id == current_user.id)
    )
    total_repos = repo_count.scalar() or 0

    # Total scans
    scan_count = await db.execute(
        select(func.count(Scan.id))
        .join(Repository)
        .where(Repository.user_id == current_user.id)
    )
    total_scans = scan_count.scalar() or 0

    # Total findings across all scans
    finding_count = await db.execute(
        select(func.count(Finding.id))
        .join(Scan)
        .join(Repository)
        .where(Repository.user_id == current_user.id)
    )
    total_findings = finding_count.scalar() or 0

    # Severity breakdown
    severity_counts = {}
    for severity in ["critical", "high", "medium", "low", "informational"]:
        count = await db.execute(
            select(func.count(Finding.id))
            .join(Scan)
            .join(Repository)
            .where(Repository.user_id == current_user.id, Finding.severity == severity)
        )
        c = count.scalar() or 0
        if c > 0:
            severity_counts[severity] = c

    # Triage breakdown
    triage_counts = {}
    for status in ["open", "false_positive", "resolved"]:
        count = await db.execute(
            select(func.count(TriageStatus.id))
            .where(TriageStatus.user_id == current_user.id, TriageStatus.status == status)
        )
        c = count.scalar() or 0
        if c > 0:
            triage_counts[status] = c

    # Top vulnerability types
    vuln_types = await db.execute(
        select(Finding.vulnerability_type, func.count(Finding.id).label("count"))
        .join(Scan)
        .join(Repository)
        .where(Repository.user_id == current_user.id)
        .group_by(Finding.vulnerability_type)
        .order_by(func.count(Finding.id).desc())
        .limit(10)
    )
    top_vulns = [{"type": row[0], "count": row[1]} for row in vuln_types.all()]

    # Language breakdown
    lang_counts = await db.execute(
        select(Finding.language, func.count(Finding.id).label("count"))
        .join(Scan)
        .join(Repository)
        .where(Repository.user_id == current_user.id)
        .group_by(Finding.language)
    )
    languages = {row[0]: row[1] for row in lang_counts.all()}

    # Recent scans
    recent = await db.execute(
        select(Scan)
        .join(Repository)
        .where(Repository.user_id == current_user.id)
        .order_by(Scan.created_at.desc())
        .limit(5)
    )
    recent_scans = [
        {
            "id": s.id,
            "repo_id": s.repo_id,
            "status": s.status,
            "files_scanned": s.files_scanned,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in recent.scalars().all()
    ]

    return {
        "success": True,
        "data": {
            "total_repos": total_repos,
            "total_scans": total_scans,
            "total_findings": total_findings,
            "severity_breakdown": severity_counts,
            "triage_breakdown": triage_counts,
            "top_vulnerability_types": top_vulns,
            "language_breakdown": languages,
            "recent_scans": recent_scans,
        },
    }
