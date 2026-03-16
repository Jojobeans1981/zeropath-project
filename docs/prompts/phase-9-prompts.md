# Phase 9 (Stretch): WebSocket Real-Time Updates — Implementation Prompts

## Prompt 9.1 — Redis Pub/Sub Service + WebSocket Endpoint

```
ROLE: You are implementing WebSocket real-time updates for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/config.py` — settings.redis_url
- `backend/app/services/auth_service.py` — decode_token(token) returns user_id
- `backend/app/models/scan.py` — Scan model
- `backend/app/models/repository.py` — Repository model
- `backend/app/database.py` — async engine, get_db()
- `redis` package in requirements.txt (has async support built-in via `redis.asyncio`)
- `backend/app/main.py` — FastAPI app

TASK:
Create Redis pub/sub service and WebSocket endpoint.

CREATE:

1. `backend/app/services/pubsub_service.py`:
   ```python
   import json
   import logging
   import redis
   import redis.asyncio as aioredis
   from app.config import settings

   logger = logging.getLogger(__name__)


   def publish_scan_event_sync(scan_id: str, event_type: str, data: dict) -> None:
       """Publish event from Celery worker (synchronous)."""
       client = redis.Redis.from_url(settings.redis_url)
       try:
           payload = json.dumps({"type": event_type, "data": data})
           client.publish(f"scan:{scan_id}:events", payload)
       finally:
           client.close()


   async def subscribe_scan_events(scan_id: str):
       """Async generator yielding events for a scan. Used by WebSocket handler."""
       client = aioredis.from_url(settings.redis_url)
       pubsub = client.pubsub()
       await pubsub.subscribe(f"scan:{scan_id}:events")

       try:
           async for message in pubsub.listen():
               if message["type"] == "message":
                   try:
                       event = json.loads(message["data"])
                       yield event
                   except json.JSONDecodeError:
                       continue
       finally:
           await pubsub.unsubscribe(f"scan:{scan_id}:events")
           await pubsub.close()
           await client.close()
   ```

2. `backend/app/routers/websocket.py`:
   ```python
   import logging
   from fastapi import APIRouter, WebSocket, WebSocketDisconnect
   from sqlalchemy import select
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
               select(Scan).join(Repository).where(Scan.id == scan_id)
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
   ```

3. MODIFY `backend/app/main.py` — add:
   ```python
   from app.routers import websocket
   app.include_router(websocket.router)
   ```

CODING STYLE:
- Async WebSocket handler
- Redis pub/sub via `redis.asyncio`
- Synchronous publisher for Celery worker
- Clean connection lifecycle (always close)

CONSTRAINTS:
- Token passed as query param (WebSocket doesn't support headers cleanly)
- Close codes: 4001 (auth), 4003 (forbidden), 4004 (not found)
- Terminal scans get one event then close
```

## Prompt 9.2 — Worker Event Publishing + Frontend WebSocket

```
ROLE: You are wiring up WebSocket events in the worker and frontend for ZeroPath Security Scanner.

CONTEXT:
- `backend/app/services/pubsub_service.py` — publish_scan_event_sync(scan_id, event_type, data)
- `backend/app/workers/scan_worker.py` — run_scan() task with steps 1-9
- `frontend/app/scans/[id]/page.tsx` — currently polls every 5 seconds
- `frontend/lib/api.ts` — has API_URL constant
- `frontend/lib/auth.ts` — getAccessToken()

Event types:
- "status_change": { status: string }
- "chunk_progress": { current: number, total: number }
- "finding_discovered": { ...FindingResponse fields }
- "scan_complete": { files_scanned: number, finding_count: number }
- "scan_failed": { error_message: string }

TASK:

1. MODIFY `backend/app/workers/scan_worker.py` — add event publishing at key pipeline steps:

   After step 2 (set running):
   ```python
   publish_scan_event_sync(scan_id, "status_change", {"status": "running"})
   ```

   After each chunk analyzed (step 7 loop):
   ```python
   publish_scan_event_sync(scan_id, "chunk_progress", {"current": i + 1, "total": len(chunks)})
   for finding_dict in findings:
       publish_scan_event_sync(scan_id, "finding_discovered", finding_dict)
   ```

   After step 9 (complete):
   ```python
   publish_scan_event_sync(scan_id, "scan_complete", {"files_scanned": len(file_contents), "finding_count": persisted_count})
   ```

   On exception:
   ```python
   publish_scan_event_sync(scan_id, "scan_failed", {"error_message": str(e)[:500]})
   ```

   Import: `from app.services.pubsub_service import publish_scan_event_sync`

   Wrap each publish in try-except (publishing failure should not fail the scan):
   ```python
   try:
       publish_scan_event_sync(...)
   except Exception:
       logger.warning("[Worker] Failed to publish event (non-fatal)")
   ```

2. MODIFY `frontend/app/scans/[id]/page.tsx`:

   Add progress state:
   ```typescript
   const [progress, setProgress] = useState<{ current: number; total: number } | null>(null);
   ```

   Replace the polling useEffect with WebSocket + polling fallback:
   ```typescript
   useEffect(() => {
     let ws: WebSocket | null = null;
     let pollInterval: NodeJS.Timeout | null = null;
     let cancelled = false;

     const fetchScan = async () => {
       // ... existing polling logic ...
     };

     const token = getAccessToken();
     if (!token) return;

     // Initial fetch
     fetchScan();

     // Try WebSocket
     const wsProtocol = API_URL.startsWith("https") ? "wss" : "ws";
     const wsBase = API_URL.replace(/^https?/, wsProtocol);
     const wsUrl = `${wsBase}/api/ws/scans/${id}?token=${token}`;

     ws = new WebSocket(wsUrl);

     ws.onopen = () => {
       // WebSocket connected, no need to poll
       if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
     };

     ws.onmessage = (event) => {
       if (cancelled) return;
       const msg = JSON.parse(event.data);
       switch (msg.type) {
         case "status_change":
           setScan(prev => prev ? { ...prev, status: msg.data.status } : prev);
           break;
         case "chunk_progress":
           setProgress(msg.data);
           break;
         case "finding_discovered":
           setFindings(prev => [...prev, msg.data]);
           break;
         case "scan_complete":
           setScan(prev => prev ? {
             ...prev,
             status: "complete",
             files_scanned: msg.data.files_scanned,
           } : prev);
           setProgress(null);
           // Fetch final findings list for accurate triage data
           fetchScan();
           break;
         case "scan_failed":
           setScan(prev => prev ? {
             ...prev,
             status: "failed",
             error_message: msg.data.error_message,
           } : prev);
           setProgress(null);
           break;
       }
     };

     ws.onerror = () => {
       // Fallback to polling
       ws?.close();
       ws = null;
       if (!cancelled && !pollInterval) {
         pollInterval = setInterval(fetchScan, 5000);
       }
     };

     ws.onclose = () => {
       ws = null;
     };

     return () => {
       cancelled = true;
       ws?.close();
       if (pollInterval) clearInterval(pollInterval);
     };
   }, [id]);
   ```

   Add progress bar UI (shown when progress is not null and scan is running):
   ```tsx
   {progress && scan?.status === "running" && (
     <div className="mb-4">
       <p className="text-sm text-gray-600 mb-1">
         Analyzing chunk {progress.current} of {progress.total}...
       </p>
       <div className="w-full bg-gray-200 rounded-full h-2">
         <div
           className="bg-blue-600 h-2 rounded-full transition-all"
           style={{ width: `${(progress.current / progress.total) * 100}%` }}
         />
       </div>
     </div>
   )}
   ```

CODING STYLE:
- Event publishing is best-effort (wrapped in try-except)
- WebSocket with polling fallback — no single point of failure
- Progressive findings: findings appear as chunks are analyzed

CONSTRAINTS:
- On scan_complete, do a final fetchScan() to get accurate triage data (WebSocket findings don't include triage)
- WebSocket protocol detection: ws:// for http://, wss:// for https://
- Cleanup: close WebSocket and clear interval on unmount
```

---

**Verification after Phase 9:**
1. WebSocket connects and receives real-time events
2. Progress bar shows chunk analysis progress
3. Findings appear progressively during scan
4. Falls back to polling if WebSocket fails
5. Already-complete scans close WebSocket immediately
