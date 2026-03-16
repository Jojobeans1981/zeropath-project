# Phase 8 (Stretch): Private Repo Auth + SARIF Export — Implementation Prompts

## Prompt 8.1 — Encrypted Token Storage + Private Clone

```
ROLE: You are adding private repository support to ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/repository.py` — Repository model (id, user_id, url, name, created_at, updated_at)
- `backend/app/schemas/repo.py` — CreateRepoRequest (url), RepoResponse, RepoDetailResponse
- `backend/app/routers/repos.py` — POST /, GET /, GET /{repo_id}
- `backend/app/scanner/git_ops.py` — clone_repo(url, dest, github_token=None) — already accepts github_token param
- `backend/app/workers/scan_worker.py` — run_scan() calls clone_repo(repo.url, temp_dir)
- `backend/app/config.py` — Settings class

TASK:
Add encrypted GitHub token storage to Repository, update create/clone flows, add migration.

1. ADD to `backend/app/config.py`:
   ```python
   repo_encryption_key: str = ""
   ```

2. CREATE `backend/app/services/crypto_service.py`:
   ```python
   from cryptography.fernet import Fernet
   from app.config import settings


   def get_fernet() -> Fernet:
       if not settings.repo_encryption_key:
           raise ValueError("REPO_ENCRYPTION_KEY environment variable is required for private repo support")
       return Fernet(settings.repo_encryption_key.encode())


   def encrypt_token(plaintext: str) -> str:
       return get_fernet().encrypt(plaintext.encode()).decode()


   def decrypt_token(ciphertext: str) -> str:
       return get_fernet().decrypt(ciphertext.encode()).decode()
   ```

3. ADD `github_token_encrypted` column to Repository model:
   ```python
   github_token_encrypted = Column(String, nullable=True)
   ```

4. Run migration: `alembic revision --autogenerate -m "add_github_token_to_repositories"` then `alembic upgrade head`

5. MODIFY `backend/app/schemas/repo.py`:
   - Add `github_token: str | None = None` to CreateRepoRequest (write-only, never returned)

6. MODIFY `backend/app/services/repo_service.py`:
   - `create_or_get_repo()`: if `github_token` provided, encrypt and store it
   - Never return the token in any response

7. MODIFY `backend/app/workers/scan_worker.py`:
   - When cloning, check if repo has `github_token_encrypted`
   - If yes, decrypt and pass to `clone_repo(repo.url, temp_dir, github_token=decrypted_token)`
   - Log `[Worker] Cloning (authenticated: True)` but NEVER log the token

8. ADD `cryptography` to `backend/requirements.txt`

9. ADD to `.env.example`:
   ```
   REPO_ENCRYPTION_KEY=  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```

CODING STYLE:
- `[Security]` log prefix for crypto operations
- NEVER log, return, or expose decrypted tokens
- Encryption key from env var, not hardcoded

CONSTRAINTS:
- Token is write-only: accepted on create, never returned in responses
- If REPO_ENCRYPTION_KEY is not set, private repos simply won't work (clear error message)
- Existing public repos are unaffected
```

## Prompt 8.2 — SARIF Export

```
ROLE: You are implementing SARIF v2.1.0 export for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/finding.py` — Finding (severity, vulnerability_type, file_path, line_number, code_snippet, description, explanation)
- `backend/app/models/scan.py` — Scan (id, repo_id, status, commit_sha)
- `backend/app/routers/scans.py` — has POST /, GET /compare, GET /{scan_id}, GET /{scan_id}/findings
- `backend/app/services/finding_service.py` — get_findings_for_scan()

TASK:
Create SARIF generation service and export endpoint.

CREATE `backend/app/services/sarif_service.py`:
```python
import re


def severity_to_level(severity: str) -> str:
    if severity in ("critical", "high"):
        return "error"
    elif severity == "medium":
        return "warning"
    return "note"


def slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def generate_sarif(scan, findings: list) -> dict:
    # Build unique rules
    rules = {}
    for f in findings:
        rule_id = slugify(f.vulnerability_type)
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": f.vulnerability_type,
                "shortDescription": {"text": f.vulnerability_type},
                "defaultConfiguration": {"level": severity_to_level(f.severity)},
            }

    # Build results
    results = []
    for f in findings:
        results.append({
            "ruleId": slugify(f.vulnerability_type),
            "level": severity_to_level(f.severity),
            "message": {"text": f.description},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file_path},
                    "region": {"startLine": f.line_number},
                }
            }],
            "properties": {
                "explanation": f.explanation,
                "severity": f.severity,
                "identityHash": f.identity_hash,
            },
        })

    return {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "ZeroPath Security Scanner",
                    "version": "1.0.0",
                    "informationUri": "https://github.com/zeropath/scanner",
                    "rules": list(rules.values()),
                }
            },
            "results": results,
        }],
    }
```

ADD to `backend/app/routers/scans.py`:
```python
from fastapi.responses import JSONResponse
from app.services import sarif_service

@router.get("/{scan_id}/sarif")
async def export_sarif(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    scan = await scan_service.get_scan(db, scan_id, current_user.id)
    if scan.status != "complete":
        raise HTTPException(status_code=400, detail={"error": {"code": "SCAN_NOT_COMPLETE", "message": "Scan must be complete to export SARIF."}})
    findings = await finding_service.get_findings_for_scan(db, scan_id, current_user.id)
    sarif = sarif_service.generate_sarif(scan, findings)
    return JSONResponse(
        content=sarif,
        headers={"Content-Disposition": f"attachment; filename=zeropath-scan-{scan_id}.sarif.json"},
    )
```

**Note:** Place this route AFTER /compare but BEFORE /{scan_id} in the router to avoid conflicts with the catch-all.

CONSTRAINTS:
- SARIF schema v2.1.0 only
- Export only available for complete scans
- Properties bag includes explanation and identity hash for tooling integration
```

## Prompt 8.3 — Frontend: Token Field + SARIF Download

```
ROLE: You are adding private repo token input and SARIF export to the ZeroPath frontend.

CONTEXT:
- `frontend/app/dashboard/page.tsx` — has "Add Repository" form with URL input
- `frontend/app/scans/[id]/page.tsx` — scan detail page
- Backend: POST /api/repos now accepts optional `github_token`, GET /api/scans/:id/sarif returns SARIF JSON

TASK:

1. MODIFY `frontend/app/dashboard/page.tsx`:
   - Add "Advanced" collapsible section below URL input
   - Toggle with "Show advanced options" text link
   - Inside: password input for GitHub token
   - Help text: "Required for private repositories. Your token is encrypted at rest and never exposed in API responses."
   - On submit: include `github_token` in POST body if provided

2. MODIFY `frontend/app/scans/[id]/page.tsx`:
   - Add "Export SARIF" button in scan header (next to StatusBadge), only visible when status === "complete"
   - On click: fetch `GET /api/scans/${id}/sarif`, create Blob, trigger download as `zeropath-scan-${id}.sarif.json`
   - Download handler:
     ```typescript
     const handleExportSarif = async () => {
       const res = await fetch(`${API_URL}/api/scans/${id}/sarif`, {
         headers: { Authorization: `Bearer ${getAccessToken()}` },
       });
       const blob = await res.blob();
       const url = window.URL.createObjectURL(blob);
       const a = document.createElement("a");
       a.href = url;
       a.download = `zeropath-scan-${id}.sarif.json`;
       a.click();
       window.URL.revokeObjectURL(url);
     };
     ```

CONSTRAINTS:
- Token field is type="password" (masked)
- SARIF download uses raw fetch (not apiFetch) since it's a file download
- "Advanced" section collapsed by default
```

---

**Verification after Phase 8:**
1. Creating repo with GitHub token encrypts and stores it
2. Private repo scans succeed with valid token
3. GET /api/scans/:id/sarif returns valid SARIF v2.1.0
4. "Export SARIF" button triggers file download
