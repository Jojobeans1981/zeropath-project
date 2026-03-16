from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.repository import Repository


def extract_repo_name(url: str) -> str:
    """Extract 'owner/repo' from a GitHub/GitLab URL."""
    parts = url.rstrip("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


async def create_or_get_repo(db: AsyncSession, user_id: str, url: str) -> Repository:
    url = url.rstrip("/").rstrip(".git")
    result = await db.execute(
        select(Repository).where(Repository.user_id == user_id, Repository.url == url)
    )
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    repo = Repository(
        user_id=user_id,
        url=url,
        name=extract_repo_name(url),
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo


async def list_repos(db: AsyncSession, user_id: str) -> list[dict]:
    # Import here to avoid circular import (Scan model may not exist yet)
    try:
        from app.models import scan as scan_module
        Scan = scan_module.Scan
        stmt = (
            select(Repository, func.count(Scan.id).label("scan_count"))
            .outerjoin(Scan, Scan.repo_id == Repository.id)
            .where(Repository.user_id == user_id)
            .group_by(Repository.id)
            .order_by(Repository.created_at.desc())
        )
        rows = await db.execute(stmt)
        return [{"repo": repo, "scan_count": count} for repo, count in rows.all()]
    except Exception:
        # Scan model doesn't exist yet (Phase 2 runs before Phase 3)
        result = await db.execute(
            select(Repository).where(Repository.user_id == user_id).order_by(Repository.created_at.desc())
        )
        return [{"repo": repo, "scan_count": 0} for repo in result.scalars().all()]


async def get_repo(db: AsyncSession, user_id: str, repo_id: str) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Repository not found."}})
    if repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})
    return repo
