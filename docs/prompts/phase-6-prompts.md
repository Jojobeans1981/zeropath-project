# Phase 6: Cross-Scan Comparison — Implementation Prompts

## Prompt 6.1 — Comparison API

```
ROLE: You are implementing the scan comparison API for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/scan.py` — Scan model (id, repo_id, status, commit_sha, etc.)
- `backend/app/models/finding.py` — Finding model (id, scan_id, identity_hash, severity, etc.)
- `backend/app/models/triage.py` — TriageStatus model
- `backend/app/services/finding_service.py` — get_findings_for_scan(), get_finding(), update_triage(), carry_forward_triage()
- `backend/app/schemas/finding.py` — FindingResponse (with triage_status, triage_notes)
- `backend/app/schemas/scan.py` — ScanResponse
- `backend/app/routers/scans.py` — has POST /, GET /{scan_id}, GET /{scan_id}/findings

API response envelope: `{"success": true, "data": ...}`

TASK:
Add comparison endpoint and schemas.

MODIFY `backend/app/schemas/scan.py` — add:
```python
from app.schemas.finding import FindingResponse

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

ADD to `backend/app/services/finding_service.py`:
```python
async def compare_scans(
    db: AsyncSession,
    base_scan_id: str,
    head_scan_id: str,
    user_id: str,
) -> dict:
    # Fetch both scans
    base_result = await db.execute(select(Scan).join(Repository).where(Scan.id == base_scan_id))
    base_scan = base_result.scalar_one_or_none()
    head_result = await db.execute(select(Scan).join(Repository).where(Scan.id == head_scan_id))
    head_scan = head_result.scalar_one_or_none()

    if not base_scan or not head_scan:
        raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found."}})

    # Verify same repo
    if base_scan.repo_id != head_scan.repo_id:
        raise HTTPException(status_code=400, detail={"error": {"code": "DIFFERENT_REPOS", "message": "Cannot compare scans from different repositories."}})

    # Verify both complete
    if base_scan.status != "complete" or head_scan.status != "complete":
        raise HTTPException(status_code=400, detail={"error": {"code": "SCAN_NOT_COMPLETE", "message": "Both scans must be complete to compare."}})

    # Verify user owns repo
    if base_scan.repo.user_id != user_id:
        raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

    # Get findings for both scans
    base_findings_result = await db.execute(select(Finding).where(Finding.scan_id == base_scan_id))
    base_findings = {f.identity_hash: f for f in base_findings_result.scalars().all()}

    head_findings_result = await db.execute(select(Finding).where(Finding.scan_id == head_scan_id))
    head_findings = {f.identity_hash: f for f in head_findings_result.scalars().all()}

    # Compute sets
    base_hashes = set(base_findings.keys())
    head_hashes = set(head_findings.keys())

    new_hashes = head_hashes - base_hashes
    fixed_hashes = base_hashes - head_hashes
    persisting_hashes = base_hashes & head_hashes

    # Build response (include triage data for current user)
    # Helper to convert finding to response dict with triage
    async def finding_to_response(finding: Finding) -> dict:
        triage_result = await db.execute(
            select(TriageStatus).where(
                TriageStatus.finding_id == finding.id,
                TriageStatus.user_id == user_id,
            )
        )
        triage = triage_result.scalar_one_or_none()
        return {
            "id": finding.id,
            "scan_id": finding.scan_id,
            "identity_hash": finding.identity_hash,
            "severity": finding.severity,
            "vulnerability_type": finding.vulnerability_type,
            "file_path": finding.file_path,
            "line_number": finding.line_number,
            "code_snippet": finding.code_snippet,
            "description": finding.description,
            "explanation": finding.explanation,
            "created_at": finding.created_at,
            "triage_status": triage.status if triage else None,
            "triage_notes": triage.notes if triage else None,
        }

    new_list = [await finding_to_response(head_findings[h]) for h in new_hashes]
    fixed_list = [await finding_to_response(base_findings[h]) for h in fixed_hashes]
    persisting_list = [await finding_to_response(head_findings[h]) for h in persisting_hashes]

    return {
        "base_scan_id": base_scan_id,
        "head_scan_id": head_scan_id,
        "counts": {"new": len(new_list), "fixed": len(fixed_list), "persisting": len(persisting_list)},
        "new": new_list,
        "fixed": fixed_list,
        "persisting": persisting_list,
    }
```

MODIFY `backend/app/routers/scans.py`:
- **IMPORTANT:** Add the compare endpoint BEFORE the `/{scan_id}` endpoint to prevent FastAPI from treating "compare" as a UUID:
```python
@router.get("/compare")
async def compare_scans_endpoint(
    base: str,
    head: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await finding_service.compare_scans(db, base, head, current_user.id)
    return {"success": True, "data": result}
```

CODING STYLE:
- Route ordering matters: /compare before /{scan_id}
- Set operations for finding categorization
- Include triage data in comparison response

CONSTRAINTS:
- Cross-repo comparison returns 400
- Incomplete scan comparison returns 400
- Self-comparison: all findings in "persisting", zero in new/fixed
```

## Prompt 6.2 — Frontend ComparisonTable + Scan Detail Extension

```
ROLE: You are implementing the comparison UI for ZeroPath Security Scanner.

CONTEXT:
The frontend has:
- `frontend/app/scans/[id]/page.tsx` — scan detail with polling, findings, filter bar, triage
- `frontend/app/repos/[id]/page.tsx` — repo detail with scan history and "New Scan" button
- `frontend/app/components/FindingCard.tsx` — expandable finding card with triage

Backend:
- `GET /api/scans/compare?base=UUID&head=UUID` → `{success: true, data: {base_scan_id, head_scan_id, counts: {new, fixed, persisting}, new: Finding[], fixed: Finding[], persisting: Finding[]}}`
- `GET /api/repos/:id` → includes scans array

TASK:
Create ComparisonTable component, add comparison UI to scan detail, and add compare links to repo detail.

CREATE:

1. `frontend/app/components/ComparisonTable.tsx`:
   ```tsx
   "use client";

   import { useState } from "react";
   import { ChevronDownIcon, ChevronRightIcon } from "@heroicons/react/24/outline";
   import { FindingCard } from "./FindingCard";

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
     triage_status: string | null;
     triage_notes: string | null;
   }

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
     onTriageUpdate?: (findingId: string, status: string, notes: string | null) => void;
   }

   interface SectionProps {
     title: string;
     subtitle: string;
     count: number;
     findings: Finding[];
     borderColor: string;
     textColor: string;
     defaultExpanded: boolean;
     onTriageUpdate?: (findingId: string, status: string, notes: string | null) => void;
   }

   function ComparisonSection({ title, subtitle, count, findings, borderColor, textColor, defaultExpanded, onTriageUpdate }: SectionProps) {
     const [expanded, setExpanded] = useState(defaultExpanded);

     return (
       <div className={`border-l-4 ${borderColor} bg-white rounded-r-lg shadow-sm`}>
         <button
           onClick={() => setExpanded(!expanded)}
           className="w-full px-4 py-3 flex items-center gap-2 text-left hover:bg-gray-50"
         >
           {expanded ? <ChevronDownIcon className="w-4 h-4" /> : <ChevronRightIcon className="w-4 h-4" />}
           <span className={`font-medium ${textColor}`}>{title} ({count})</span>
         </button>
         {!expanded && <p className="px-4 pb-2 text-xs text-gray-500 pl-10">{subtitle}</p>}
         {expanded && (
           <div className="px-4 pb-4 space-y-2">
             <p className="text-xs text-gray-500 mb-2">{subtitle}</p>
             {findings.map((f) => (
               <FindingCard key={f.id} finding={f} onTriageUpdate={onTriageUpdate} />
             ))}
             {findings.length === 0 && (
               <p className="text-sm text-gray-400 italic">None</p>
             )}
           </div>
         )}
       </div>
     );
   }

   export function ComparisonTable({ data, onTriageUpdate }: ComparisonTableProps) {
     return (
       <div className="space-y-4">
         <ComparisonSection
           title="New Findings"
           subtitle="Vulnerabilities found in the latest scan that weren't in the previous scan"
           count={data.counts.new}
           findings={data.new}
           borderColor="border-red-500"
           textColor="text-red-700"
           defaultExpanded={data.counts.new > 0}
           onTriageUpdate={onTriageUpdate}
         />
         <ComparisonSection
           title="Fixed Findings"
           subtitle="Vulnerabilities from the previous scan that are no longer present"
           count={data.counts.fixed}
           findings={data.fixed}
           borderColor="border-green-500"
           textColor="text-green-700"
           defaultExpanded={data.counts.fixed > 0}
           onTriageUpdate={onTriageUpdate}
         />
         <ComparisonSection
           title="Persisting Findings"
           subtitle="Vulnerabilities present in both scans"
           count={data.counts.persisting}
           findings={data.persisting}
           borderColor="border-gray-400"
           textColor="text-gray-700"
           defaultExpanded={data.counts.persisting > 0}
           onTriageUpdate={onTriageUpdate}
         />
       </div>
     );
   }
   ```

2. MODIFY `frontend/app/scans/[id]/page.tsx`:

   Add comparison state and UI:
   ```typescript
   const [compareWith, setCompareWith] = useState<string | null>(null);
   const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
   const [comparingLoading, setComparingLoading] = useState(false);
   const [otherScans, setOtherScans] = useState<Scan[]>([]);
   ```

   After loading the scan (when status is complete), fetch other scans for the same repo:
   ```typescript
   // Fetch other scans for comparison dropdown
   if (res.data.status === "complete" && res.data.repo_id) {
     const repoRes = await apiFetch<RepoDetail>(`/api/repos/${res.data.repo_id}`);
     if (repoRes.success && repoRes.data) {
       setOtherScans(repoRes.data.scans.filter(s => s.id !== id && s.status === "complete"));
     }
   }
   ```

   Add comparison handler:
   ```typescript
   const handleCompare = async (baseScanId: string) => {
     setComparingLoading(true);
     setCompareWith(baseScanId);
     const res = await apiFetch<ComparisonData>(`/api/scans/compare?base=${baseScanId}&head=${id}`);
     if (res.success && res.data) setComparisonData(res.data);
     setComparingLoading(false);
   };
   ```

   Add comparison UI below scan header, above findings:
   - "Compare with..." select dropdown listing otherScans
   - When comparison is active: show ComparisonTable instead of regular findings list
   - "Clear comparison" button to reset

   Check URL for `?compare=` query param on mount and auto-trigger comparison.

3. MODIFY `frontend/app/repos/[id]/page.tsx`:

   Between consecutive completed scans in the scan history, add "Compare ↔" link:
   - Only between scans where both are "complete"
   - On click: navigate to `/scans/${newer.id}?compare=${older.id}`

CODING STYLE:
- ComparisonTable is a self-contained named export component
- Sections are collapsible, default-expanded if count > 0
- Query param `?compare=` enables deep-linking to comparisons

CONSTRAINTS:
- ComparisonTable reuses FindingCard for individual findings
- Filter bar is hidden during comparison view (comparison has its own categorization)
- "Clear comparison" returns to normal findings view with filter bar
```

---

**Verification after Phase 6:**
1. GET /api/scans/compare?base=X&head=Y returns correctly categorized findings
2. ComparisonTable renders three sections with correct color coding
3. "Compare with..." dropdown works on scan detail page
4. "Compare ↔" links appear between completed scans on repo page
5. Deep-link via ?compare= query param auto-triggers comparison
