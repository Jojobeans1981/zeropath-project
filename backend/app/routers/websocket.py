import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import async_session_maker
from app.models.scan import Scan
from app.models.repository import Repository
from app.services.auth_service import decode_token
from app.services.pubsub_service import subscribe_scan_events

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/api/ws/scans/{scan_id}")
async def scan_websocket(websocket: WebSocket, scan_id: str):
    # Extract token from query params
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    # Validate token
    try:
        user_id = decode_token(token)
    except Exception:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Verify scan exists and belongs to user
    async with async_session_maker() as db:
        result = await db.execute(
            select(Scan).options(selectinload(Scan.repo)).where(Scan.id == scan_id)
        )
        scan = result.scalar_one_or_none()

        if not scan:
            await websocket.close(code=4004, reason="Scan not found")
            return
        if scan.repo.user_id != user_id:
            await websocket.close(code=4003, reason="Access denied")
            return

        current_status = scan.status

    await websocket.accept()

    # If scan is already terminal, send current state and close
    if current_status in ("complete", "failed"):
        await websocket.send_json({"type": f"scan_{current_status}", "data": {"status": current_status}})
        await websocket.close()
        return

    # Subscribe to events
    try:
        async for event in subscribe_scan_events(scan_id):
            await websocket.send_json(event)
            # Close on terminal events
            if event["type"] in ("scan_complete", "scan_failed"):
                await websocket.close()
                return
    except WebSocketDisconnect:
        logger.info("[WebSocket] Client disconnected from scan %s", scan_id)
    except Exception as e:
        logger.error("[WebSocket] Error for scan %s: %s", scan_id, str(e))
        try:
            await websocket.close(code=1011, reason="Internal error")
        except Exception:
            pass
