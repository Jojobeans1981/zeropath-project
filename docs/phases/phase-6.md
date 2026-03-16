# Phase 6: Cross-Scan Comparison

## Objective
Build the scan comparison feature that shows which findings are new, fixed, or persisting between two scans of the same repo — the key feature for tracking security posture over time.

## Current State (After Phase 5)
- **Backend:** Full API: auth (4), repos (3), scans (POST, GET/:id, GET/:id/findings), findings (GET/:id, PATCH/:id/triage). Triage carry-forward in worker. Models: User, Repository, Scan, Finding, TriageStatus.
- **Frontend:** Login/signup, dashboard, repo detail (scan history + new scan), scan detail (polling + findings + filter bar), FindingCard (expandable + triage controls), SeverityBadge, StatusBadge, NavHeader.
- **Database:** SQLite with `users`, `repositories`, `scans`, `findings`, `triage_statuses` tables.
- **Key files:** `backend/app/services/finding_service.py`, `backend/app/routers/scans.py`, `frontend/app/scans/[id]/page.tsx`, `frontend/app/repos/[id]/page.tsx`

## Architecture Context

### New API Endpoint
| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/api/scans/compare` | Yes | `?base=:uuid&head=:uuid` | ComparisonResponse |

### ComparisonResponse Shape
```json
{
  "base_scan_id": "uuid",
  "head_scan_id": "uuid",
  "counts": {
    "new": 3,
    "fixed": 1,
    "persisting": 8
  },
  "new": [ FindingResponse, ... ],
  "fixed": [ FindingResponse, ... ],
  "persisting": [ FindingResponse, ... ]
}
```

### Comparison Logic
Given two completed scans (base and head) of the same repo:
- Get the set of `identity_hash` values for each scan
- **new** = hashes in head that are NOT in base → return Finding objects from the head scan
- **fixed** = hashes in base that are NOT in head → return Finding objects from the base scan
- **persisting** = hashes in BOTH base and head → return Finding objects from the head scan (with current triage)

## Coding Standards

### Python Backend
- File naming: lowercase snake_case
- All handlers: `async def`
- Pydantic schemas for request/response

### TypeScript Frontend
- `"use client"`, interfaces at top, no `any`
- `useState` for comparison state
- `apiFetch<T>()` for API calls
- Tailwind utility classes
- ComparisonTable as a separate named-export component

## Deliverables

1. **`backend/app/services/finding_service.py`** (extend) — add `compare_scans()` method
2. **`backend/app/schemas/scan.py`** (extend) — add `ComparisonResponse`
3. **`backend/app/routers/scans.py`** (extend) — add `GET /compare` endpoint
4. **`frontend/app/components/ComparisonTable.tsx`** — three-section comparison view
5. **`frontend/app/scans/[id]/page.tsx`** (extend) — comparison UI with scan selector
6. **`frontend/app/repos/[id]/page.tsx`** (extend) — compare links between scans

## Technical Specification

### backend/app/services/finding_service.py (extend)

- `compare_scans(db, base_scan_id, head_scan_id, user_id) -> dict`:
  1. Fetch both scans. Verify both exist → 404 if not.
  2. Verify both scans belong to the same repo → 400 `{ code: "DIFFERENT_REPOS", message: "Cannot compare scans from different repositories." }`
  3. Verify both scans are `complete` → 400 `{ code: "SCAN_NOT_COMPLETE", message: "Both scans must be complete to compare." }`
  4. Verify user owns the repo (through either scan) → 403
  5. Query all findings for base scan: `{ identity_hash: Finding }` dict
  6. Query all findings for head scan: `{ identity_hash: Finding }` dict
  7. Compute sets:
     ```python
     base_hashes = set(base_findings.keys())
     head_hashes = set(head_findings.keys())
     new_hashes = head_hashes - base_hashes
     fixed_hashes = base_hashes - head_hashes
     persisting_hashes = base_hashes & head_hashes
     ```
  8. Build response:
     - `new`: findings from head scan where hash in `new_hashes`
     - `fixed`: findings from base scan where hash in `fixed_hashes`
     - `persisting`: findings from head scan where hash in `persisting_hashes`
  9. Include triage data (join TriageStatus for current user)

### backend/app/schemas/scan.py (extend)

Add:
```python
class ComparisonCounts(BaseModel):
    new: int
    fixed: int
    persisting: int

class ComparisonResponse(BaseModel):
    base_scan_id: str
    head_scan_id: str
    counts: ComparisonCounts
    new: list[FindingResponse]
    fixed: list[FindingResponse]
    persisting: list[FindingResponse]
```

### backend/app/routers/scans.py (extend)

- `GET /compare`:
  - Query params: `base` (UUID string), `head` (UUID string)
  - **Important:** This route must be defined BEFORE the `GET /{scan_id}` route, otherwise FastAPI will try to parse "compare" as a scan_id UUID and fail.
  - Call `finding_service.compare_scans(db, base, head, current_user.id)`
  - Return `{ success: true, data: ComparisonResponse }`

### frontend/app/components/ComparisonTable.tsx

Named export `ComparisonTable`. Props:
```typescript
interface ComparisonData {
  base_scan_id: string;
  head_scan_id: string;
  counts: { new: number; fixed: number; persisting: number };
  new: Finding[];
  fixed: Finding[];
  persisting: Finding[];
}

interface ComparisonTableProps {
  data: ComparisonData;
}
```

Three collapsible sections:

1. **New Findings** — left border red (`border-l-4 border-red-500`)
   - Header: "New Findings ({count})" with red text
   - Subtitle: "Vulnerabilities found in the latest scan that weren't in the previous scan"
   - Lists FindingCard components for each finding
   - Collapsed by default if count is 0

2. **Fixed Findings** — left border green (`border-l-4 border-green-500`)
   - Header: "Fixed Findings ({count})" with green text
   - Subtitle: "Vulnerabilities from the previous scan that are no longer present"
   - Lists FindingCard components
   - Collapsed by default if count is 0

3. **Persisting Findings** — left border gray (`border-l-4 border-gray-400`)
   - Header: "Persisting Findings ({count})" with gray text
   - Subtitle: "Vulnerabilities present in both scans"
   - Lists FindingCard components

Each section is collapsible with a chevron toggle. State: `expandedSections` as `Set<string>` — default: expand sections with count > 0.

### frontend/app/scans/[id]/page.tsx (extend)

Add comparison UI below the scan header, above the findings list:

1. **"Compare with..." dropdown**: A `<select>` listing other completed scans for the same repo.
   - Fetch scan list from the repo detail endpoint (already available from Phase 4)
   - Exclude the current scan from the dropdown
   - Options format: "Scan from {date} ({finding_count} findings)"
   - Default: "Select a scan to compare..."

2. When a comparison scan is selected:
   - Fetch `GET /api/scans/compare?base={selected_scan_id}&head={current_scan_id}`
   - State: `comparisonData` (ComparisonData | null), `comparingLoading` (boolean)
   - Render `<ComparisonTable data={comparisonData} />` instead of the regular findings list
   - Add a "Clear comparison" button to return to normal findings view

3. State management:
   - `compareWith` (string | null) — selected scan ID
   - `comparisonData` (ComparisonData | null) — fetched comparison result
   - `comparingLoading` (boolean)

### frontend/app/repos/[id]/page.tsx (extend)

Between consecutive completed scans in the scan history list, add a small "Compare ↔" link.

```
┌──────────────────────────────────────┐
│ [COMPLETE] Scan - Mar 16   23 findings │
│                   Compare ↔           │
│ [COMPLETE] Scan - Mar 15   20 findings │
│                   Compare ↔           │
│ [COMPLETE] Scan - Mar 14   18 findings │
└──────────────────────────────────────┘
```

Clicking "Compare ↔" navigates to `/scans/{newer_scan_id}?compare={older_scan_id}`.

On the scan detail page, check for `compare` query param on mount. If present, auto-select that scan in the comparison dropdown and trigger the comparison fetch.

## Acceptance Criteria

1. `GET /api/scans/compare?base=X&head=Y` returns correctly categorized findings
2. Self-comparison (base=X, head=X) returns all findings as `persisting`, zero `new` and `fixed`
3. A finding in base but not head appears in `fixed`
4. A finding in head but not base appears in `new`
5. A finding in both appears in `persisting` (with head scan's data and triage)
6. Cross-repo comparison returns 400 with `DIFFERENT_REPOS` error
7. Comparing incomplete scans returns 400 with `SCAN_NOT_COMPLETE` error
8. ComparisonTable renders three color-coded sections with correct counts
9. Sections with zero items are collapsed by default
10. "Compare with..." dropdown on scan page lists other completed scans
11. Selecting a comparison scan fetches and displays comparison data
12. "Clear comparison" button returns to normal findings view
13. "Compare ↔" links on repo page navigate to scan detail with comparison pre-selected
