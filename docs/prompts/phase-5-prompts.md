# Phase 5: Triage Workflow — Implementation Prompts

## Prompt 5.1 — TriageStatus Model + Migration

```
ROLE: You are implementing the TriageStatus model for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/finding.py` — Finding model (id, scan_id, identity_hash, severity, etc.)
- `backend/app/models/user.py` — User model (id, email, etc.), exports utcnow()
- `backend/app/models/__init__.py` — imports User, Repository, Scan, Finding
- `backend/app/database.py` — exports Base, engines, sessions

TASK:
Create the TriageStatus model and run migration.

CREATE:

1. `backend/app/models/triage.py`:
   ```python
   import uuid
   from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
   from sqlalchemy.dialects.sqlite import CHAR
   from sqlalchemy.orm import relationship
   from app.database import Base
   from app.models.user import utcnow


   class TriageStatus(Base):
       __tablename__ = "triage_statuses"
       __table_args__ = (
           UniqueConstraint("finding_id", "user_id", name="uq_finding_user_triage"),
       )

       id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       finding_id = Column(CHAR(36), ForeignKey("findings.id"), index=True, nullable=False)
       user_id = Column(CHAR(36), ForeignKey("users.id"), index=True, nullable=False)
       status = Column(String, nullable=False, default="open")
       notes = Column(String, nullable=True)
       created_at = Column(DateTime, default=utcnow)
       updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

       finding = relationship("Finding", backref="triage_records")
       user = relationship("User")
   ```

2. MODIFY `backend/app/models/__init__.py`:
   ```python
   from app.models.user import User
   from app.models.repository import Repository
   from app.models.scan import Scan
   from app.models.finding import Finding
   from app.models.triage import TriageStatus

   __all__ = ["User", "Repository", "Scan", "Finding", "TriageStatus"]
   ```

3. Run: `alembic revision --autogenerate -m "create_triage_statuses_table"` then `alembic upgrade head`

CONSTRAINTS:
- UniqueConstraint ensures one triage status per finding per user (upsert pattern)
- Status values: "open", "false_positive", "resolved"
- Do NOT create API endpoints yet
```

## Prompt 5.2 — Triage API + Finding Response Extension

```
ROLE: You are implementing the triage API and extending finding responses for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/triage.py` — TriageStatus model (id, finding_id, user_id, status, notes, created_at, updated_at)
- `backend/app/schemas/finding.py` — FindingResponse (does not include triage fields yet)
- `backend/app/services/finding_service.py` — get_findings_for_scan(), get_finding()
- `backend/app/routers/findings.py` — GET /{finding_id}

TASK:
Add triage endpoint, extend FindingResponse with triage fields, and update finding queries to include triage data.

MODIFY:

1. `backend/app/schemas/finding.py` — add:
   ```python
   class TriageRequest(BaseModel):
       status: str
       notes: str | None = None

       @field_validator("status")
       @classmethod
       def validate_status(cls, v: str) -> str:
           if v not in {"open", "false_positive", "resolved"}:
               raise ValueError("Status must be one of: open, false_positive, resolved")
           return v
   ```
   And extend FindingResponse to add:
   ```python
   triage_status: str | None = None
   triage_notes: str | None = None
   ```

2. `backend/app/services/finding_service.py` — add method:
   ```python
   async def update_triage(
       db: AsyncSession,
       finding_id: str,
       user_id: str,
       status: str,
       notes: str | None = None,
   ) -> TriageStatus:
       # Verify finding exists and user owns the repo
       finding = await get_finding(db, finding_id, user_id)

       # Upsert triage status
       result = await db.execute(
           select(TriageStatus).where(
               TriageStatus.finding_id == finding_id,
               TriageStatus.user_id == user_id,
           )
       )
       triage = result.scalar_one_or_none()

       if triage:
           triage.status = status
           triage.notes = notes
       else:
           triage = TriageStatus(
               finding_id=finding_id,
               user_id=user_id,
               status=status,
               notes=notes,
           )
           db.add(triage)

       await db.commit()
       await db.refresh(triage)
       return triage
   ```

   Also modify `get_findings_for_scan()` to join-load triage for the current user. For each finding, check if a TriageStatus exists and populate triage_status/triage_notes. Similarly for `get_finding()`.

3. `backend/app/routers/findings.py` — add:
   ```python
   @router.patch("/{finding_id}/triage")
   async def triage_finding(
       finding_id: str,
       req: TriageRequest,
       current_user: User = Depends(get_current_user),
       db: AsyncSession = Depends(get_db),
   ):
       triage = await finding_service.update_triage(
           db, finding_id, current_user.id, req.status, req.notes
       )
       return {
           "success": True,
           "data": {
               "status": triage.status,
               "notes": triage.notes,
               "updated_at": triage.updated_at.isoformat() if triage.updated_at else None,
           },
       }
   ```

CODING STYLE:
- Upsert pattern: check existing, update or create
- Import field_validator from pydantic for schema validation
- Response envelope on triage endpoint

CONSTRAINTS:
- Triage data is per-user-per-finding (supports multi-user, future RBAC)
- The FindingResponse triage fields default to None (untriaged)
```

## Prompt 5.3 — Triage Carry-Forward in Worker

```
ROLE: You are implementing triage carry-forward logic for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/triage.py` — TriageStatus (finding_id, user_id, status, notes)
- `backend/app/models/finding.py` — Finding (identity_hash is the key for cross-scan matching)
- `backend/app/models/scan.py` — Scan (repo_id, status, created_at)
- `backend/app/workers/scan_worker.py` — run_scan() task, uses SyncSessionLocal, persists findings in step 8
- `backend/app/database.py` — SyncSessionLocal for sync sessions

TASK:
Add a carry_forward_triage function and call it from the worker after findings are persisted.

ADD to `backend/app/services/finding_service.py`:
```python
def carry_forward_triage(sync_db, scan_id: str) -> int:
    """Copy triage statuses from previous scan's findings to current scan's findings with matching identity_hash.
    Uses synchronous DB session (called from Celery worker).
    Returns count of carried-forward statuses."""
    from app.models.scan import Scan
    from app.models.finding import Finding
    from app.models.triage import TriageStatus

    # Get current scan
    current_scan = sync_db.query(Scan).filter(Scan.id == scan_id).first()
    if not current_scan:
        return 0

    # Find previous completed scan for same repo
    previous_scan = (
        sync_db.query(Scan)
        .filter(
            Scan.repo_id == current_scan.repo_id,
            Scan.id != scan_id,
            Scan.status == "complete",
        )
        .order_by(Scan.created_at.desc())
        .first()
    )
    if not previous_scan:
        return 0

    # Get current scan's findings
    current_findings = sync_db.query(Finding).filter(Finding.scan_id == scan_id).all()
    current_hash_map = {f.identity_hash: f for f in current_findings}

    # Get previous scan's findings with triage
    prev_findings = sync_db.query(Finding).filter(Finding.scan_id == previous_scan.id).all()

    carried = 0
    for prev_finding in prev_findings:
        if prev_finding.identity_hash not in current_hash_map:
            continue

        current_finding = current_hash_map[prev_finding.identity_hash]

        # Get triage records for previous finding
        triage_records = (
            sync_db.query(TriageStatus)
            .filter(TriageStatus.finding_id == prev_finding.id)
            .all()
        )

        for triage in triage_records:
            new_triage = TriageStatus(
                finding_id=current_finding.id,
                user_id=triage.user_id,
                status=triage.status,
                notes=triage.notes,
            )
            sync_db.add(new_triage)
            carried += 1

    sync_db.commit()
    return carried
```

MODIFY `backend/app/workers/scan_worker.py`:
- Import `carry_forward_triage` from `app.services.finding_service`
- After step 8 (persist findings), before step 9 (mark complete), add:
  ```python
  # 8.5. Carry forward triage from previous scan
  try:
      carried = carry_forward_triage(db, scan_id)
      logger.info("[Worker] Carried forward %d triage statuses", carried)
  except Exception as e:
      logger.warning("[Worker] Triage carry-forward failed (non-fatal): %s", str(e))
  ```

CODING STYLE:
- Synchronous code (runs in Celery worker)
- db.query() for sync SQLAlchemy
- Best-effort: wrapped in try-except, failure doesn't fail the scan

CONSTRAINTS:
- This is a sync function, not async (Celery worker context)
- Carry-forward is best-effort — log warning on failure, don't raise
```

## Prompt 5.4 — Frontend Triage UI + Filters

```
ROLE: You are extending the frontend with triage controls and filter bar for ZeroPath Security Scanner.

CONTEXT:
The frontend has:
- `frontend/app/components/FindingCard.tsx` — expandable card showing severity, vuln type, file:line, description, explanation, code snippet. No triage controls yet.
- `frontend/app/scans/[id]/page.tsx` — scan detail page with polling and findings list
- `frontend/lib/api.ts` — apiFetch<T>()

Backend:
- `PATCH /api/findings/:id/triage` body: `{status: "open"|"false_positive"|"resolved", notes?: string}` → `{success: true, data: {status, notes, updated_at}}`
- Finding responses now include: `triage_status: string | null`, `triage_notes: string | null`

TASK:
Add triage controls to FindingCard and a filter bar to the scan detail page.

MODIFY `frontend/app/components/FindingCard.tsx`:

1. Update Finding interface to include:
   ```typescript
   triage_status: string | null;
   triage_notes: string | null;
   ```

2. Add new prop: `onTriageUpdate?: (findingId: string, status: string, notes: string | null) => void`

3. Add state: `triageStatus` (string, init from finding.triage_status || ""), `triageNotes` (string, init from finding.triage_notes || ""), `saving` (boolean)

4. In collapsed header (next to SeverityBadge), add triage badge:
   - If triage_status === "open": gray outline badge showing "Open"
   - If triage_status === "false_positive": yellow outline badge showing "FP"
   - If triage_status === "resolved": green outline badge showing "Resolved"
   - If null: no badge

5. In expanded section (after explanation and code), add triage controls:
   ```tsx
   <div className="border-t border-gray-100 pt-3 mt-3">
     <p className="text-sm font-medium text-gray-700 mb-2">Triage</p>
     <div className="flex gap-2 mb-2">
       {["open", "false_positive", "resolved"].map((s) => (
         <button
           key={s}
           onClick={() => setTriageStatus(s)}
           className={`px-3 py-1 rounded text-xs font-medium border ${
             triageStatus === s
               ? "bg-gray-900 text-white border-gray-900"
               : "bg-white text-gray-700 border-gray-300 hover:bg-gray-50"
           }`}
         >
           {s === "false_positive" ? "False Positive" : s.charAt(0).toUpperCase() + s.slice(1)}
         </button>
       ))}
     </div>
     <textarea
       value={triageNotes}
       onChange={(e) => setTriageNotes(e.target.value)}
       placeholder="Optional notes..."
       className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm resize-none"
       rows={2}
     />
     <button
       onClick={handleSaveTriage}
       disabled={saving || !triageStatus}
       className="mt-2 px-4 py-1.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50"
     >
       {saving ? "Saving..." : "Save Triage"}
     </button>
   </div>
   ```

6. handleSaveTriage:
   - Set saving=true
   - Call `apiFetch("/api/findings/${finding.id}/triage", {method: "PATCH", body: JSON.stringify({status: triageStatus, notes: triageNotes || null})})`
   - On success: call onTriageUpdate callback
   - Set saving=false

MODIFY `frontend/app/scans/[id]/page.tsx`:

1. Update Finding interface to include triage_status, triage_notes

2. Add filter state:
   ```typescript
   const [triageFilter, setTriageFilter] = useState<string>("all");
   const [severityFilter, setSeverityFilter] = useState<string>("all");
   ```

3. Add filter bar above findings list:
   - Two groups of pill buttons separated by a pipe character
   - Group 1 (triage): All, Open, False Positive, Resolved
   - Group 2 (severity): All, Critical, High, Medium, Low, Info
   - Active pill: `bg-gray-900 text-white`, inactive: `bg-gray-100 text-gray-700 hover:bg-gray-200`
   - Show count in "All": `All ({findings.length})`

4. Filter logic (client-side):
   ```typescript
   const filteredFindings = findings.filter((f) => {
     if (triageFilter !== "all" && (f.triage_status || "open") !== triageFilter) return false;
     if (severityFilter !== "all" && f.severity !== severityFilter) return false;
     return true;
   });
   ```

5. Render filteredFindings instead of findings

6. Add onTriageUpdate callback:
   ```typescript
   const handleTriageUpdate = (findingId: string, status: string, notes: string | null) => {
     setFindings((prev) =>
       prev.map((f) =>
         f.id === findingId ? { ...f, triage_status: status, triage_notes: notes } : f
       )
     );
   };
   ```
   Pass to each FindingCard.

CODING STYLE:
- All filter operations are client-side (no API calls for filtering)
- Triage save triggers API call and updates local state via callback
- Pill buttons for filters, not dropdowns

CONSTRAINTS:
- Default triage_status for untriaged findings: treat as "open" for filtering
- Filters combine: triage AND severity
```

---

**Verification after Phase 5:**
1. PATCH /api/findings/:id/triage saves and returns triage data
2. GET /api/scans/:id/findings includes triage_status and triage_notes
3. FindingCard shows triage badge and triage controls work
4. Filter bar filters by triage status and severity
5. Triage carry-forward works on re-scan
