from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.scan import Scan
from app.models.repository import Repository


async def create_scan(db: AsyncSession, repo_id: str, user_id: str) -> Scan:
    # Verify repo exists and belongs to user
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Repository not found."}})
    if repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    scan = Scan(repo_id=repo_id, status="queued")
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    # Enqueue Celery task
    from app.workers.scan_worker import run_scan
    run_scan.delay(scan.id)

    return scan


async def get_scan(db: AsyncSession, scan_id: str, user_id: str) -> Scan:
    result = await db.execute(
        select(Scan).options(selectinload(Scan.repo)).where(Scan.id == scan_id)
    )
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found."}})
    if scan.repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})
    return scan
