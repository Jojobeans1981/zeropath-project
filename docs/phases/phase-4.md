# Phase 4: Findings Dashboard & Scan Results UI

## Objective
Build the frontend views for scan results: trigger scans from UI, poll for status, display findings with full detail, and show scan metadata.

## Current State (After Phase 3)
- **Backend:** Full auth + repo management + scanning pipeline. Endpoints: health, auth (4), repos (3), scans (POST create, GET status). Celery worker runs full scan pipeline (clone → chunk → analyze → dedup → persist). Models: User, Repository, Scan, Finding.
- **Frontend:** Login/signup, dashboard (repo list + add form), repo detail (basic — shows repo info + placeholder), NavHeader.
- **Database:** SQLite with `users`, `repositories`, `scans`, `findings` tables.
- **Key files:** `backend/app/routers/scans.py` (POST + GET/:id), `backend/app/schemas/finding.py` (FindingResponse defined), `frontend/app/repos/[id]/page.tsx` (has placeholder for scan history), `frontend/app/components/NavHeader.tsx`

## Architecture Context

### New API Endpoints
| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/api/scans/:id/findings` | Yes | `?severity=critical,high` (optional) | Array of FindingResponse |
| GET | `/api/findings/:id` | Yes | — | FindingResponse |

### Existing Schemas (from Phase 3)

ScanResponse:
```json
{
  "id": "uuid", "repo_id": "uuid", "status": "complete",
  "commit_sha": "abc123...", "error_message": null,
  "files_scanned": 15, "started_at": "...", "completed_at": "...", "created_at": "..."
}
```

FindingResponse:
```json
{
  "id": "uuid", "scan_id": "uuid", "identity_hash": "sha256...",
  "severity": "high", "vulnerability_type": "SQL Injection",
  "file_path": "app/db.py", "line_number": 42,
  "code_snippet": "cursor.execute(f\"SELECT * FROM users WHERE id = {user_id}\")",
  "description": "SQL injection via string formatting in database query.",
  "explanation": "User input is directly interpolated into a SQL query...",
  "created_at": "..."
}
```

### Repos Detail Extension
The repo detail page (`/repos/[id]`) currently shows basic repo info. This phase adds:
- List of scans with status badges
- "New Scan" button
- Each scan links to `/scans/[id]`

## Coding Standards

### TypeScript Frontend
- `"use client"` on interactive pages
- Interfaces at top of file, no `any`
- `useState` + `useEffect` for data fetching
- Polling: `useEffect` with `setInterval`, clear on unmount or terminal status
- `apiFetch<T>()` for all API calls
- Loading skeletons with `animate-pulse`
- Tailwind utility classes
- Components: named exports, PascalCase files

### Python Backend
- Async handlers, Pydantic schemas
- Response envelope: `{ success, data/error }`

## Deliverables

1. **`backend/app/routers/scans.py`** (extend) — add `GET /:id/findings` endpoint
2. **`backend/app/routers/findings.py`** — `GET /:id` finding detail
3. **`backend/app/services/finding_service.py`** — finding query methods
4. **`frontend/app/components/SeverityBadge.tsx`** — color-coded severity indicator
5. **`frontend/app/components/StatusBadge.tsx`** — scan status indicator
6. **`frontend/app/components/FindingCard.tsx`** — expandable finding card
7. **`frontend/app/scans/[id]/page.tsx`** — scan detail page with polling + findings
8. **`frontend/app/repos/[id]/page.tsx`** (extend) — add scan history + new scan button

## Technical Specification

### backend/app/services/finding_service.py
- `get_findings_for_scan(db, scan_id, user_id, severity_filter=None) -> list[Finding]`:
  1. Verify scan belongs to user (join through repo)
  2. Query findings where `scan_id` matches
  3. If `severity_filter` provided (comma-separated string), filter by those severities
  4. Order by severity priority: critical → high → medium → low → informational
  5. Return findings list

- `get_finding(db, finding_id, user_id) -> Finding`:
  1. Get finding, join through scan→repo, verify user owns repo
  2. Return finding or raise 404

### backend/app/routers/scans.py (extend)
- Add `GET /{scan_id}/findings`:
  - Query param: `severity` (optional, comma-separated: `"critical,high"`)
  - Call `finding_service.get_findings_for_scan()`
  - Return `{ success: true, data: FindingResponse[] }`

### backend/app/routers/findings.py
- Router prefix: `/api/findings`
- `GET /{finding_id}`: call `finding_service.get_finding()`, return wrapped `FindingResponse`

### backend/app/main.py (modify)
- Add: `from app.routers import findings`
- Add: `app.include_router(findings.router)`

### frontend/app/components/SeverityBadge.tsx

Named export `SeverityBadge`. Props: `{ severity: string }`.

Color mapping:
- `critical` → `bg-red-100 text-red-800 border-red-200`
- `high` → `bg-orange-100 text-orange-800 border-orange-200`
- `medium` → `bg-yellow-100 text-yellow-800 border-yellow-200`
- `low` → `bg-blue-100 text-blue-800 border-blue-200`
- `informational` → `bg-gray-100 text-gray-800 border-gray-200`

Render: `<span className="px-2 py-0.5 rounded text-xs font-medium border {colors}">{severity}</span>`

### frontend/app/components/StatusBadge.tsx

Named export `StatusBadge`. Props: `{ status: string }`.

Color mapping:
- `queued` → `bg-gray-100 text-gray-700`
- `running` → `bg-blue-100 text-blue-700 animate-pulse`
- `complete` → `bg-green-100 text-green-700`
- `failed` → `bg-red-100 text-red-700`

Render: `<span className="px-2 py-0.5 rounded text-xs font-medium {colors}">{status}</span>`

### frontend/app/components/FindingCard.tsx

Named export `FindingCard`. Props: `{ finding: Finding }` where Finding matches FindingResponse interface.

- Default state: collapsed — shows severity badge, vulnerability type, `file_path:line_number`, description truncated to 2 lines
- Expanded state (toggle on click): shows full description, full explanation in a styled block, code snippet in a monospace `<pre>` block with gray background
- Expand/collapse indicated by a chevron icon from `@heroicons/react`
- State: `expanded` (boolean) via `useState`

Layout:
```
┌─────────────────────────────────────────────────┐
│ [HIGH] SQL Injection    app/db.py:42            │
│ SQL injection via string formatting in...       │
├─────────────────────────────────────────────────┤
│ (expanded)                                       │
│ Explanation: User input is directly...           │
│                                                  │
│ ┌─ Code ──────────────────────────────────┐     │
│ │ cursor.execute(f"SELECT * FROM...")      │     │
│ └─────────────────────────────────────────┘     │
└─────────────────────────────────────────────────┘
```

### frontend/app/scans/[id]/page.tsx

- `"use client"`, auth guard, `useParams()` to get scan ID
- Interfaces: `Scan` (matching ScanResponse), `Finding` (matching FindingResponse)
- State: `scan` (Scan | null), `findings` (Finding[]), `loading` (boolean), `error` (string)

**Polling logic:**
```typescript
useEffect(() => {
  const fetchScan = async () => {
    const res = await apiFetch<Scan>(`/api/scans/${id}`);
    if (res.success && res.data) {
      setScan(res.data);
      if (res.data.status === "complete") {
        // Fetch findings
        const findingsRes = await apiFetch<Finding[]>(`/api/scans/${id}/findings`);
        if (findingsRes.success && findingsRes.data) setFindings(findingsRes.data);
      }
    }
  };
  fetchScan();
  const interval = setInterval(() => {
    if (scan?.status === "queued" || scan?.status === "running") fetchScan();
    else clearInterval(interval);
  }, 5000);
  return () => clearInterval(interval);
}, [id, scan?.status]);
```

**Render sections:**
1. NavHeader
2. Back link to repo: `← Back to {repo_name}`
3. Scan header: status badge, commit SHA (truncated to 7 chars), files scanned count, started/completed timestamps
4. While queued/running: "Scan in progress..." with a spinner or pulsing indicator
5. When failed: red error box showing `scan.error_message`
6. When complete with findings: list of FindingCard components
7. When complete with zero findings: green box — "No vulnerabilities found" with a check icon

### frontend/app/repos/[id]/page.tsx (extend)

Add after the repo info section:
1. **"New Scan" button:** Calls `POST /api/scans` with `{ repo_id: id }`. On success, `router.push(/scans/${data.id})`. Show loading state while creating.
2. **Scan history list:** Fetch scans from `GET /api/repos/:id` (the backend should include recent scans in repo detail response — extend `RepoResponse` and `get_repo` to include an array of scans, ordered newest first).
   - Each scan row: StatusBadge, date (relative like "2 hours ago" or formatted), finding count, link to `/scans/{scan.id}`
   - Empty state: "No scans yet. Click 'New Scan' to analyze this repository."

### backend/app/routers/repos.py (extend)
- `GET /api/repos/:id` should now include `scans` array in response. Extend `get_repo` to join-load scans (ordered by `created_at` desc). Add `scans: list[ScanResponse]` to the repo detail response (create a `RepoDetailResponse` schema).

### backend/app/schemas/repo.py (extend)
- Add `RepoDetailResponse(BaseModel)`: inherits all fields from `RepoResponse` plus `scans: list[ScanResponse]`
- Import `ScanResponse` from `schemas/scan.py`

## Acceptance Criteria

1. `GET /api/scans/:id/findings` returns findings array sorted by severity
2. `GET /api/scans/:id/findings?severity=critical,high` returns only critical and high findings
3. `GET /api/findings/:id` returns full finding detail
4. Repo detail page shows scan history ordered newest first
5. "New Scan" button creates scan and navigates to scan detail page
6. Scan detail page polls every 5 seconds while scan is queued/running
7. Polling stops when scan reaches terminal state (complete/failed)
8. Findings render with severity badge, vuln type, file:line, description
9. Clicking a finding card expands to show explanation + code snippet
10. Failed scans show error message in red box
11. Zero-finding scans show "No vulnerabilities found" message
12. Severity badges use correct colors (red/orange/yellow/blue/gray)
