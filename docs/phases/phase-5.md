# Phase 5: Triage Workflow

## Objective
Enable users to mark findings as open, false positive, or resolved with optional notes — the core triage workflow that makes the tool actionable for AppSec engineers.

## Current State (After Phase 4)
- **Backend:** Full API: auth (4 endpoints), repos (3), scans (POST, GET/:id, GET/:id/findings), findings (GET/:id). Scanner pipeline with Celery. Models: User, Repository, Scan, Finding.
- **Frontend:** Login/signup, dashboard (repo list + add), repo detail (with scan history + new scan button), scan detail (with polling + findings list), FindingCard (expandable), SeverityBadge, StatusBadge, NavHeader.
- **Database:** SQLite with `users`, `repositories`, `scans`, `findings` tables.
- **Key files:** `backend/app/routers/findings.py` (GET /:id), `backend/app/services/finding_service.py` (get_findings_for_scan, get_finding), `backend/app/schemas/finding.py` (FindingResponse), `frontend/app/components/FindingCard.tsx`, `frontend/app/scans/[id]/page.tsx`

## Architecture Context

### Data Model: TriageStatus
```
TriageStatus
├── id: UUID (PK)
├── finding_id: UUID (FK → findings.id, indexed)
├── user_id: UUID (FK → users.id, indexed)
├── status: String (enum: "open", "false_positive", "resolved")
├── notes: String (nullable)
├── created_at: DateTime (UTC)
├── updated_at: DateTime (UTC, auto-updates)
└── UNIQUE constraint on (finding_id, user_id)
```

### New/Modified API Endpoints
| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| PATCH | `/api/findings/:id/triage` | Yes | `{ status: string, notes?: string }` | Updated triage data |

### FindingResponse Extension
FindingResponse now includes:
```json
{
  ...existing fields...,
  "triage_status": "open" | "false_positive" | "resolved" | null,
  "triage_notes": "string or null"
}
```

### Triage Carry-Forward Logic
When a scan completes and findings are persisted, for each new finding:
1. Look up the most recent Scan (before the current one) for the same Repository
2. In that prior scan's findings, find one with the same `identity_hash`
3. If found and that finding has a TriageStatus record for the current user, copy the `status` and `notes` to a new TriageStatus for the new finding

This happens in the Celery worker, after findings are persisted.

## Coding Standards

### Python Backend
- File naming: lowercase snake_case
- All handlers: `async def`
- Logging: `[Triage]` prefix
- Pydantic schemas for all request/response

### TypeScript Frontend
- `"use client"`, interfaces at top, no `any`
- `useState` for triage state in FindingCard
- `apiFetch<T>()` for PATCH call
- Tailwind utility classes

## Deliverables

1. **`backend/app/models/triage.py`** — TriageStatus SQLAlchemy model
2. **Alembic migration** — creates `triage_statuses` table
3. **`backend/app/schemas/finding.py`** (extend) — add `TriageRequest`, extend `FindingResponse`
4. **`backend/app/services/finding_service.py`** (extend) — add triage upsert + carry-forward
5. **`backend/app/routers/findings.py`** (extend) — add PATCH triage endpoint
6. **`backend/app/workers/scan_worker.py`** (extend) — call carry-forward after persisting findings
7. **`frontend/app/components/FindingCard.tsx`** (extend) — add triage controls
8. **`frontend/app/scans/[id]/page.tsx`** (extend) — add filter bar

## Technical Specification

### backend/app/models/triage.py
- Table name: `triage_statuses`
- Columns as specified in data model above
- `__table_args__` = `(UniqueConstraint("finding_id", "user_id", name="uq_finding_user_triage"),)`
- Relationship: `finding = relationship("Finding", backref="triage_records")`
- Relationship: `user = relationship("User")`

### backend/app/models/__init__.py (modify)
- Import TriageStatus for Alembic autogenerate

### backend/app/schemas/finding.py (extend)
- Add `TriageRequest(BaseModel)`: `status: str` (must be one of "open", "false_positive", "resolved"), `notes: str | None = None`
- Add validator on `status`: must be in `{"open", "false_positive", "resolved"}`
- Extend `FindingResponse` to include: `triage_status: str | None = None`, `triage_notes: str | None = None`

### backend/app/services/finding_service.py (extend)

- `update_triage(db, finding_id, user_id, status, notes=None) -> TriageStatus`:
  1. Verify finding exists and user owns the repo (through scan→repo)
  2. Query for existing TriageStatus with `finding_id` + `user_id`
  3. If exists: update `status` and `notes`, update `updated_at`
  4. If not: create new TriageStatus record
  5. Commit and return

- `get_findings_for_scan(...)` (modify): join-load TriageStatus for the current user. Populate `triage_status` and `triage_notes` fields in FindingResponse.

- `get_finding(...)` (modify): same — include triage data in response.

- `carry_forward_triage(sync_db, scan_id)`:
  - This runs in the Celery worker (synchronous DB session)
  - Get the current scan and its repo_id
  - Get the previous completed scan for this repo (most recent before current scan, ordered by `created_at desc`)
  - If no previous scan, return early
  - For each finding in the current scan:
    1. Look up findings in the previous scan with matching `identity_hash`
    2. If found, get TriageStatus records for that previous finding
    3. For each TriageStatus record, create a new one for the current finding with same `user_id`, `status`, `notes`
  - Log: `[Triage] Carried forward {count} triage statuses from scan {prev_id}`

### backend/app/routers/findings.py (extend)
- `PATCH /{finding_id}/triage`:
  - Body: `TriageRequest`
  - Call `finding_service.update_triage(db, finding_id, current_user.id, req.status, req.notes)`
  - Return `{ success: true, data: { status, notes, updated_at } }`

### backend/app/workers/scan_worker.py (extend)
- After step 8 (persist findings), before step 9 (set complete):
  - Call `carry_forward_triage(sync_db, scan.id)`
  - This is a best-effort operation — if it fails, log warning but don't fail the scan

### frontend/app/components/FindingCard.tsx (extend)

Add triage controls inside the expanded section:

```
┌─────────────────────────────────────────────────┐
│ [HIGH] [OPEN] SQL Injection    app/db.py:42     │
│ SQL injection via string formatting in...       │
├─────────────────────────────────────────────────┤
│ (expanded)                                       │
│ Explanation: ...                                │
│ ┌─ Code ────────────────────────────────┐       │
│ │ cursor.execute(...)                    │       │
│ └───────────────────────────────────────┘       │
│                                                  │
│ Triage:                                         │
│ [Status: ▾ Open/False Positive/Resolved]        │
│ [Notes: ________________________________]       │
│ [Save Triage]                                   │
└─────────────────────────────────────────────────┘
```

- New props: `onTriageUpdate?: (findingId: string, status: string, notes: string) => void`
- State: `triageStatus` (string), `triageNotes` (string), `saving` (boolean)
- Initialize from `finding.triage_status` / `finding.triage_notes`
- "Save Triage" button: call `apiFetch` with PATCH, then call `onTriageUpdate` callback
- Small triage status badge next to severity badge in collapsed view:
  - `open` → gray outline badge
  - `false_positive` → yellow outline badge with "FP" text
  - `resolved` → green outline badge with "✓" text
  - `null` (untriaged) → no badge shown

### frontend/app/scans/[id]/page.tsx (extend)

Add filter bar above findings list:

```
[All] [Open] [False Positive] [Resolved] | [All] [Critical] [High] [Medium] [Low] [Info]
```

- State: `triageFilter` (string: "all" | "open" | "false_positive" | "resolved"), `severityFilter` (string: "all" | specific severity)
- Render as horizontal row of pill-style buttons. Active pill: `bg-gray-900 text-white`. Inactive: `bg-gray-100 text-gray-700 hover:bg-gray-200`.
- Pipe separator `|` between the two filter groups
- Client-side filtering: filter `findings` array before mapping to FindingCard components
- Show count next to "All" pill: e.g. "All (23)"

## Acceptance Criteria

1. `PATCH /api/findings/:id/triage` with `{ status: "false_positive", notes: "Not exploitable in this context" }` returns 200 and persists
2. Calling PATCH again with different status updates the existing record (upsert, not duplicate)
3. `GET /api/scans/:id/findings` includes `triage_status` and `triage_notes` per finding
4. FindingCard shows triage status badge in collapsed view
5. Expanded FindingCard has status dropdown, notes textarea, and save button
6. Saving triage updates the badge without full page reload
7. Filter bar filters findings by triage status (client-side)
8. Filter bar filters findings by severity (client-side)
9. Filters can be combined (e.g. "open" + "critical" shows only open critical findings)
10. When a new scan completes, findings with matching identity_hash inherit triage from the previous scan
11. Triage carry-forward failure does not fail the scan
