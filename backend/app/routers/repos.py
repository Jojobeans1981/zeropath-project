from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models.scan import Scan
from app.models.user import User
from app.schemas.repo import CreateRepoRequest, RepoResponse, RepoDetailResponse
from app.schemas.scan import ScanResponse
from app.services import repo_service

router = APIRouter(prefix="/api/repos", tags=["repos"])


@router.post("/")
async def create_repo(
    req: CreateRepoRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "member"])),
):
    repo = await repo_service.create_or_get_repo(db, current_user.id, req.url, req.github_token)
    data = RepoResponse(
        id=repo.id,
        url=repo.url,
        name=repo.name,
        scan_count=0,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )
    return {"success": True, "data": data.model_dump()}


@router.get("/")
async def list_repos(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    results = await repo_service.list_repos(db, current_user.id)
    data = [
        RepoResponse(
            id=r["repo"].id,
            url=r["repo"].url,
            name=r["repo"].name,
            scan_count=r["scan_count"],
            created_at=r["repo"].created_at,
            updated_at=r["repo"].updated_at,
        ).model_dump()
        for r in results
    ]
    return {"success": True, "data": data}


@router.get("/{repo_id}")
async def get_repo(
    repo_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = await repo_service.get_repo(db, current_user.id, repo_id)

    # Fetch scans for this repo
    result = await db.execute(
        select(Scan).where(Scan.repo_id == repo_id).order_by(Scan.created_at.desc())
    )
    scans = result.scalars().all()

    scan_responses = [
        ScanResponse(
            id=s.id,
            repo_id=s.repo_id,
            status=s.status,
            commit_sha=s.commit_sha,
            error_message=s.error_message,
            files_scanned=s.files_scanned,
            started_at=s.started_at,
            completed_at=s.completed_at,
            created_at=s.created_at,
        )
        for s in scans
    ]

    data = RepoDetailResponse(
        id=repo.id,
        url=repo.url,
        name=repo.name,
        scan_count=len(scans),
        scans=scan_responses,
        created_at=repo.created_at,
        updated_at=repo.updated_at,
    )
    return {"success": True, "data": data.model_dump()}
