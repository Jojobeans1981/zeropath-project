# Phase 9 (Stretch): WebSocket Real-Time Updates

## Objective
Replace polling with WebSocket connections for live scan status and progressive finding display during scan execution.

## Current State (After Phase 8)
- **Backend:** Complete API with auth, repos (with private token support), scans (with SARIF export), findings, triage, comparison. Celery worker pipeline.
- **Frontend:** Full dashboard with polling-based scan status updates (5-second interval).
- **Current behavior:** Scan detail page polls `GET /api/scans/:id` every 5 seconds while status is queued/running. Findings only appear after scan completes.

## Architecture Context

### WebSocket Flow
```
Frontend                    Backend                    Redis                     Worker
   │                          │                          │                        │
   ├─WS /api/ws/scans/:id───→│                          │                        │
   │  (with ?token=JWT)       │                          │                        │
   │                          ├──subscribe──────────────→│                        │
   │                          │  channel: scan:{id}      │                        │
   │                          │                          │                        │
   │                          │                          │←──publish──────────────┤
   │                          │                          │  status_change: running│
   │←──event: status_change───┤←──receive───────────────┤                        │
   │                          │                          │                        │
   │                          │                          │←──publish──────────────┤
   │                          │                          │  chunk_progress: 2/5   │
   │←──event: chunk_progress──┤←──receive───────────────┤                        │
   │                          │                          │                        │
   │                          │                          │←──publish──────────────┤
   │                          │                          │  finding: {...}        │
   │←──event: finding─────────┤←──receive───────────────┤                        │
   │                          │                          │                        │
   │                          │                          │←──publish──────────────┤
   │                          │                          │  scan_complete         │
   │←──event: complete────────┤←──receive───────────────┤                        │
   │←──connection closed──────┤                          │                        │
```

### Event Types
```json
{ "type": "status_change", "data": { "status": "running", "timestamp": "..." } }
{ "type": "chunk_progress", "data": { "current": 2, "total": 5 } }
{ "type": "finding_discovered", "data": { ...FindingResponse... } }
{ "type": "scan_complete", "data": { "files_scanned": 15, "finding_count": 8 } }
{ "type": "scan_failed", "data": { "error_message": "..." } }
```

## Coding Standards
- Python: async WebSocket handler, Redis pub/sub via `aioredis`
- TypeScript: `useEffect` for WebSocket lifecycle, reconnection logic
- Fallback to polling if WebSocket fails

## Deliverables

1. **`backend/app/routers/websocket.py`** — WebSocket endpoint
2. **`backend/app/services/pubsub_service.py`** — Redis pub/sub helpers
3. **`backend/app/workers/scan_worker.py`** (extend) — publish events during pipeline
4. **`frontend/app/scans/[id]/page.tsx`** (extend) — WebSocket connection with polling fallback
5. **`backend/requirements.txt`** (extend) — add `aioredis` or use `redis.asyncio`

## Technical Specification

### backend/app/services/pubsub_service.py
- Uses `redis.asyncio` (already have `redis` package, the async client is built-in)
- `publish_scan_event(scan_id: str, event_type: str, data: dict)`:
  - Publish to Redis channel `scan:{scan_id}:events`
  - Payload: JSON string of `{ "type": event_type, "data": data }`
- `subscribe_scan_events(scan_id: str)` → async generator:
  - Subscribe to channel `scan:{scan_id}:events`
  - Yield parsed events as they arrive

For the Celery worker (synchronous context):
- `publish_scan_event_sync(scan_id: str, event_type: str, data: dict)`:
  - Uses synchronous `redis.Redis` client
  - Same channel and payload format

### backend/app/routers/websocket.py
- `WS /api/ws/scans/{scan_id}`:
  1. Extract `token` from query params: `?token=<JWT>`
  2. Validate JWT → close with 4001 code if invalid
  3. Verify scan belongs to user → close with 4003 if not
  4. Check scan status: if already terminal (complete/failed), send final state and close
  5. Subscribe to Redis channel via `pubsub_service.subscribe_scan_events(scan_id)`
  6. Forward events to client as JSON
  7. On `scan_complete` or `scan_failed` event: send event, then close connection
  8. Handle client disconnect gracefully

### backend/app/workers/scan_worker.py (extend)
Add event publishing at key pipeline steps:
- After step 1 (set running): `publish_scan_event_sync(scan_id, "status_change", {"status": "running"})`
- After each chunk analyzed (step 5): `publish_scan_event_sync(scan_id, "chunk_progress", {"current": i+1, "total": total_chunks})`
- For each finding discovered: `publish_scan_event_sync(scan_id, "finding_discovered", {finding_data})`
- After step 9 (complete): `publish_scan_event_sync(scan_id, "scan_complete", {"files_scanned": n, "finding_count": m})`
- On failure: `publish_scan_event_sync(scan_id, "scan_failed", {"error_message": str(e)})`

### backend/app/main.py (modify)
- Add: `from app.routers import websocket`
- Add: `app.include_router(websocket.router)`

### frontend/app/scans/[id]/page.tsx (extend)

Replace polling with WebSocket, with polling fallback:

```typescript
useEffect(() => {
  let ws: WebSocket | null = null;
  let pollInterval: NodeJS.Timeout | null = null;

  const token = getAccessToken();
  if (!token) return;

  // Try WebSocket first
  const wsUrl = `${API_URL.replace('http', 'ws')}/api/ws/scans/${id}?token=${token}`;
  ws = new WebSocket(wsUrl);

  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
      case "status_change":
        setScan(prev => prev ? { ...prev, status: msg.data.status } : prev);
        break;
      case "chunk_progress":
        setProgress(msg.data); // { current, total }
        break;
      case "finding_discovered":
        setFindings(prev => [...prev, msg.data]);
        break;
      case "scan_complete":
        setScan(prev => prev ? { ...prev, status: "complete", files_scanned: msg.data.files_scanned } : prev);
        break;
      case "scan_failed":
        setScan(prev => prev ? { ...prev, status: "failed", error_message: msg.data.error_message } : prev);
        break;
    }
  };

  ws.onerror = () => {
    // Fallback to polling
    ws?.close();
    pollInterval = setInterval(fetchScan, 5000);
  };

  return () => {
    ws?.close();
    if (pollInterval) clearInterval(pollInterval);
  };
}, [id]);
```

**New UI elements:**
- Progress bar: when `chunk_progress` events arrive, show "Analyzing chunk {current}/{total}" with a progress bar
- Progressive findings: findings appear in the list as `finding_discovered` events arrive, before scan completes
- State: `progress` (`{ current: number, total: number } | null`)

## Acceptance Criteria

1. WebSocket connects with valid JWT token
2. Invalid token → WebSocket closes with 4001 code
3. Status change events arrive in real-time (no 5-second delay)
4. Chunk progress events show analysis progress
5. Findings appear progressively as chunks are analyzed
6. Connection closes cleanly when scan completes or fails
7. If WebSocket connection fails, falls back to 5-second polling
8. Already-complete scans: WebSocket sends current state and closes immediately
9. Multiple clients can connect to the same scan's WebSocket
10. Worker publishes events at all key pipeline steps
