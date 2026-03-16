import logging
from fastapi import APIRouter, Request, HTTPException
from sqlalchemy import select
from app.config import settings
from app.database import async_session_maker
from app.models.repository import Repository
from app.models.scan import Scan
from app.services.webhook_service import verify_github_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/github")
async def github_webhook(request: Request):
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=501, detail="Webhooks not configured")

    # Verify signature
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not verify_github_signature(body, signature, settings.github_webhook_secret):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse event
    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type != "push":
        return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

    payload = await request.json()
    clone_url = payload.get("repository", {}).get("clone_url", "")
    # Normalize: strip .git suffix
    repo_url = clone_url.rstrip(".git").rstrip("/")

    # Find matching repo
    async with async_session_maker() as db:
        result = await db.execute(
            select(Repository).where(Repository.url == repo_url)
        )
        repo = result.scalar_one_or_none()

        if not repo:
            logger.info("[Webhook] No tracked repo matches %s", repo_url)
            return {"status": "ignored", "reason": "Repository not tracked"}

        # Create scan
        scan = Scan(repo_id=repo.id, status="queued")
        db.add(scan)
        await db.commit()
        await db.refresh(scan)

        # Enqueue task
        from app.workers.scan_worker import run_scan
        run_scan.delay(scan.id)

        logger.info("[Webhook] Triggered scan %s for repo %s", scan.id, repo.name)
        return {"status": "ok", "scan_id": scan.id}
