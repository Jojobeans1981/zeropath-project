# Phase 4: Findings Dashboard & Scan Results UI — Implementation Prompts

## Prompt 4.1 — Findings API Endpoints

```
ROLE: You are implementing the findings API endpoints for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/finding.py` — Finding model (id, scan_id, identity_hash, severity, vulnerability_type, file_path, line_number, code_snippet, description, explanation, created_at, updated_at)
- `backend/app/models/scan.py` — Scan model (id, repo_id, status, commit_sha, etc.)
- `backend/app/models/repository.py` — Repository model (id, user_id, url, name)
- `backend/app/schemas/finding.py` — FindingResponse (id, scan_id, identity_hash, severity, vulnerability_type, file_path, line_number, code_snippet, description, explanation, created_at)
- `backend/app/schemas/scan.py` — ScanResponse
- `backend/app/routers/scans.py` — has POST / and GET /{scan_id}
- `backend/app/deps.py` — get_current_user(), get_db()
- `backend/app/main.py` — includes auth, repos, scans routers

API response envelope: `{"success": true, "data": ...}` or `{"success": false, "error": {"code", "message"}}`

TASK:
Add findings endpoints and extend the repo detail to include scans.

CREATE:

1. `backend/app/services/finding_service.py`:
   ```python
   from fastapi import HTTPException
   from sqlalchemy import select
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.models.finding import Finding
   from app.models.scan import Scan
   from app.models.repository import Repository

   SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


   async def get_findings_for_scan(
       db: AsyncSession,
       scan_id: str,
       user_id: str,
       severity_filter: str | None = None,
   ) -> list[Finding]:
       # Verify scan belongs to user
       result = await db.execute(
           select(Scan).join(Repository).where(Scan.id == scan_id)
       )
       scan = result.scalar_one_or_none()
       if not scan:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found."}})
       if scan.repo.user_id != user_id:
           raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

       stmt = select(Finding).where(Finding.scan_id == scan_id)

       if severity_filter:
           severities = [s.strip().lower() for s in severity_filter.split(",")]
           stmt = stmt.where(Finding.severity.in_(severities))

       result = await db.execute(stmt)
       findings = list(result.scalars().all())

       # Sort by severity priority
       findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 5))
       return findings


   async def get_finding(db: AsyncSession, finding_id: str, user_id: str) -> Finding:
       result = await db.execute(
           select(Finding)
           .join(Scan)
           .join(Repository)
           .where(Finding.id == finding_id)
       )
       finding = result.scalar_one_or_none()
       if not finding:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Finding not found."}})
       if finding.scan.repo.user_id != user_id:
           raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})
       return finding
   ```

2. MODIFY `backend/app/routers/scans.py` — add endpoint:
   ```python
   @router.get("/{scan_id}/findings")
   async def get_scan_findings(
       scan_id: str,
       severity: str | None = None,
       current_user: User = Depends(get_current_user),
       db: AsyncSession = Depends(get_db),
   ):
       findings = await finding_service.get_findings_for_scan(db, scan_id, current_user.id, severity)
       return {"success": True, "data": [FindingResponse(...) for f in findings]}
   ```
   Map each Finding model to FindingResponse by extracting all fields.

3. CREATE `backend/app/routers/findings.py`:
   - Router prefix `/api/findings`, tags `["findings"]`
   - `GET /{finding_id}`: call finding_service.get_finding(), return wrapped FindingResponse

4. MODIFY `backend/app/main.py` — add:
   ```python
   from app.routers import findings
   app.include_router(findings.router)
   ```

5. MODIFY `backend/app/schemas/repo.py` — add:
   ```python
   from app.schemas.scan import ScanResponse

   class RepoDetailResponse(BaseModel):
       id: str
       url: str
       name: str
       scan_count: int = 0
       scans: list[ScanResponse] = []
       created_at: datetime
       updated_at: datetime
   ```

6. MODIFY `backend/app/routers/repos.py` — update `GET /{repo_id}` endpoint:
   - After getting repo, query scans for this repo ordered by created_at desc
   - Return RepoDetailResponse with scans array populated
   - Include finding count per scan (optional, or just return scan data)

CODING STYLE:
- Async handlers, select() with joins for ownership verification
- Sort findings by severity priority (critical first)
- Response envelope on all endpoints

CONSTRAINTS:
- FindingResponse does not include triage fields yet — that's Phase 5
- The severity filter is optional, comma-separated
```

## Prompt 4.2 — Frontend Components (Badges + FindingCard)

```
ROLE: You are implementing reusable UI components for ZeroPath Security Scanner.

CONTEXT:
The frontend has:
- `frontend/app/components/NavHeader.tsx` — navigation header
- Tailwind CSS configured
- `@heroicons/react` package available

TASK:
Create SeverityBadge, StatusBadge, and FindingCard components.

CREATE:

1. `frontend/app/components/SeverityBadge.tsx`:
   ```tsx
   "use client";

   interface SeverityBadgeProps {
     severity: string;
   }

   const SEVERITY_COLORS: Record<string, string> = {
     critical: "bg-red-100 text-red-800 border-red-200",
     high: "bg-orange-100 text-orange-800 border-orange-200",
     medium: "bg-yellow-100 text-yellow-800 border-yellow-200",
     low: "bg-blue-100 text-blue-800 border-blue-200",
     informational: "bg-gray-100 text-gray-800 border-gray-200",
   };

   export function SeverityBadge({ severity }: SeverityBadgeProps) {
     const colors = SEVERITY_COLORS[severity] || SEVERITY_COLORS.informational;
     return (
       <span className={`px-2 py-0.5 rounded text-xs font-medium border ${colors}`}>
         {severity}
       </span>
     );
   }
   ```

2. `frontend/app/components/StatusBadge.tsx`:
   ```tsx
   "use client";

   interface StatusBadgeProps {
     status: string;
   }

   const STATUS_COLORS: Record<string, string> = {
     queued: "bg-gray-100 text-gray-700",
     running: "bg-blue-100 text-blue-700 animate-pulse",
     complete: "bg-green-100 text-green-700",
     failed: "bg-red-100 text-red-700",
   };

   export function StatusBadge({ status }: StatusBadgeProps) {
     const colors = STATUS_COLORS[status] || STATUS_COLORS.queued;
     return (
       <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors}`}>
         {status}
       </span>
     );
   }
   ```

3. `frontend/app/components/FindingCard.tsx`:
   ```tsx
   "use client";

   import { useState } from "react";
   import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
   import { SeverityBadge } from "./SeverityBadge";

   interface Finding {
     id: string;
     scan_id: string;
     identity_hash: string;
     severity: string;
     vulnerability_type: string;
     file_path: string;
     line_number: number;
     code_snippet: string;
     description: string;
     explanation: string;
     created_at: string;
   }

   interface FindingCardProps {
     finding: Finding;
   }

   export function FindingCard({ finding }: FindingCardProps) {
     const [expanded, setExpanded] = useState(false);

     return (
       <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
         {/* Collapsed header — always visible */}
         <button
           onClick={() => setExpanded(!expanded)}
           className="w-full px-4 py-3 flex items-center gap-3 text-left hover:bg-gray-50"
         >
           {expanded ? (
             <ChevronDownIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
           ) : (
             <ChevronRightIcon className="w-4 h-4 text-gray-400 flex-shrink-0" />
           )}
           <SeverityBadge severity={finding.severity} />
           <span className="font-medium text-sm text-gray-900">{finding.vulnerability_type}</span>
           <span className="text-xs text-gray-500 ml-auto">
             {finding.file_path}:{finding.line_number}
           </span>
         </button>

         {/* Collapsed description */}
         {!expanded && (
           <p className="px-4 pb-3 text-sm text-gray-600 line-clamp-2 pl-11">
             {finding.description}
           </p>
         )}

         {/* Expanded detail */}
         {expanded && (
           <div className="px-4 pb-4 pl-11 space-y-3 border-t border-gray-100 pt-3">
             <div>
               <p className="text-sm font-medium text-gray-700 mb-1">Description</p>
               <p className="text-sm text-gray-600">{finding.description}</p>
             </div>
             <div>
               <p className="text-sm font-medium text-gray-700 mb-1">Explanation</p>
               <p className="text-sm text-gray-600">{finding.explanation}</p>
             </div>
             <div>
               <p className="text-sm font-medium text-gray-700 mb-1">Code</p>
               <pre className="bg-gray-900 text-gray-100 text-xs p-3 rounded-lg overflow-x-auto">
                 <code>{finding.code_snippet}</code>
               </pre>
             </div>
           </div>
         )}
       </div>
     );
   }
   ```

CODING STYLE:
- Named exports for all components
- `"use client"` on each file
- Interfaces at top of file
- Tailwind utility classes
- Heroicons for expand/collapse icons

CONSTRAINTS:
- FindingCard does NOT have triage controls yet — those are added in Phase 5
- No API calls in these components — they're pure display components
```

## Prompt 4.3 — Scan Detail Page

```
ROLE: You are implementing the scan detail page with polling for ZeroPath Security Scanner.

CONTEXT:
The frontend has:
- `frontend/lib/api.ts` — apiFetch<T>() wrapper
- `frontend/lib/auth.ts` — getAccessToken()
- `frontend/app/components/NavHeader.tsx`, `SeverityBadge.tsx`, `StatusBadge.tsx`, `FindingCard.tsx`
- FindingCard expects a Finding object: {id, scan_id, identity_hash, severity, vulnerability_type, file_path, line_number, code_snippet, description, explanation, created_at}

Backend endpoints:
- `GET /api/scans/:id` → `{success: true, data: ScanResponse}` with status, commit_sha, files_scanned, started_at, completed_at
- `GET /api/scans/:id/findings?severity=...` → `{success: true, data: FindingResponse[]}`

TASK:
Create the scan detail page with polling during queued/running states.

CREATE:

1. `frontend/app/scans/[id]/page.tsx`:
   - `"use client"` directive
   - Interfaces:
     ```typescript
     interface Scan {
       id: string;
       repo_id: string;
       status: string;
       commit_sha: string | null;
       error_message: string | null;
       files_scanned: number;
       started_at: string | null;
       completed_at: string | null;
       created_at: string;
     }

     interface Finding {
       id: string;
       scan_id: string;
       identity_hash: string;
       severity: string;
       vulnerability_type: string;
       file_path: string;
       line_number: number;
       code_snippet: string;
       description: string;
       explanation: string;
       created_at: string;
     }
     ```

   - State: scan (Scan | null), findings (Finding[]), loading (boolean), error (string)

   - Auth guard: useEffect checking getAccessToken(), redirect to /login if missing

   - Polling logic:
     ```typescript
     useEffect(() => {
       let interval: NodeJS.Timeout | null = null;

       const fetchScan = async () => {
         const res = await apiFetch<Scan>(`/api/scans/${id}`);
         if (res.success && res.data) {
           setScan(res.data);
           if (res.data.status === "complete") {
             const findingsRes = await apiFetch<Finding[]>(`/api/scans/${id}/findings`);
             if (findingsRes.success && findingsRes.data) {
               setFindings(findingsRes.data);
             }
           }
         } else {
           setError(res.error?.message || "Failed to load scan.");
         }
         setLoading(false);
       };

       fetchScan();
       interval = setInterval(() => {
         if (!scan || scan.status === "queued" || scan.status === "running") {
           fetchScan();
         } else if (interval) {
           clearInterval(interval);
         }
       }, 5000);

       return () => { if (interval) clearInterval(interval); };
     }, [id]);
     ```

   - Render:
     - NavHeader
     - max-w-4xl mx-auto px-4 py-8 container
     - Back link: "← Back" (links to /repos/{scan.repo_id} if available)
     - Scan header card:
       - StatusBadge, commit SHA (truncated to 7 chars), files scanned count
       - Started/completed timestamps formatted
     - If queued or running: centered pulsing blue text "Scan in progress... Analyzing repository for security vulnerabilities."
     - If failed: red error box with scan.error_message
     - If complete with findings: map to FindingCard components
     - If complete with zero findings: green box "No vulnerabilities found" with check icon
     - Loading state: skeleton cards

CODING STYLE:
- `"use client"`, useParams() from next/navigation for the id
- Polling interval: 5 seconds, cleared on unmount or terminal state
- Date formatting: `new Date(dateStr).toLocaleString()`
- Severity badge count summary above findings list (e.g. "3 critical, 5 high, 2 medium")

CONSTRAINTS:
- Do NOT add triage controls — that's Phase 5
- Do NOT add comparison UI — that's Phase 6
- Polling uses setInterval, not setTimeout recursion
```

## Prompt 4.4 — Repo Detail: Scan History + New Scan

```
ROLE: You are extending the repo detail page to show scan history and a "New Scan" button for ZeroPath Security Scanner.

CONTEXT:
The frontend has:
- `frontend/app/repos/[id]/page.tsx` — currently shows basic repo info and a placeholder for scan history
- `frontend/app/components/StatusBadge.tsx` — scan status indicator
- `frontend/lib/api.ts` — apiFetch<T>()

Backend endpoints:
- `GET /api/repos/:id` → now returns `{success: true, data: {id, url, name, scan_count, scans: [{id, repo_id, status, commit_sha, files_scanned, started_at, completed_at, created_at}, ...], created_at, updated_at}}`
- `POST /api/scans` body: `{repo_id}` → `{success: true, data: ScanResponse}`

TASK:
Rewrite the repo detail page to include scan history and a "New Scan" button.

MODIFY `frontend/app/repos/[id]/page.tsx`:

- Add interfaces: Scan (matching ScanResponse), RepoDetail (with scans array)
- New state: scanLoading (boolean) for the "New Scan" button
- On mount: fetch GET /api/repos/${id} (response now includes scans array)

- "New Scan" button:
  - Positioned next to the repo heading
  - On click: POST /api/scans with {repo_id: id}
  - On success: router.push(`/scans/${data.id}`) to navigate to the new scan
  - Disabled while scanLoading, shows "Starting Scan..."

- Scan history section (below repo info):
  - Heading: "Scan History"
  - List of scans ordered newest first
  - Each scan row: a clickable card linking to /scans/{scan.id}
    - StatusBadge, date (formatted), files scanned count, commit SHA (7 chars)
    - For complete scans: show finding count if available
  - Empty state: "No scans yet. Click 'New Scan' to analyze this repository."
  - Loading state: skeleton cards

- Keep existing: NavHeader, back link to dashboard, repo name heading, URL link

CODING STYLE:
- Same patterns as existing page
- Use Link from next/link for scan row navigation
- StatusBadge for each scan's status

CONSTRAINTS:
- Do NOT add comparison links — that's Phase 6
- Each scan card links to /scans/{scan.id}
```

---

**Verification after Phase 4:**
1. GET /api/scans/:id/findings returns findings sorted by severity
2. GET /api/scans/:id/findings?severity=critical,high filters correctly
3. Scan detail page polls every 5 seconds during queued/running
4. Findings render with expandable cards
5. Repo detail page shows scan history and "New Scan" button works
6. Complete flow: add repo → new scan → poll → see findings
