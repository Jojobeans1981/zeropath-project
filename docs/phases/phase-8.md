# Phase 8 (Stretch): Private Repo Auth + SARIF Export

## Objective
Support scanning private GitHub repos via personal access tokens, and export findings in SARIF v2.1.0 format for GitHub Code Scanning integration.

## Current State (After Phase 7)
- **Backend:** Complete REST API with auth, repos, scans, findings, triage, comparison. Full scanner pipeline with Celery. Tests passing.
- **Frontend:** Complete dashboard UI with all core features. Polished loading/error/empty states.
- **Database:** SQLite with 5 tables: users, repositories, scans, findings, triage_statuses.
- **Deployment:** Configured for Vercel (frontend) + Railway (backend).
- **All Phase 0-7 features complete and tested.**

## Architecture Context

### Schema Changes
Add to Repository model:
```
Repository (extend)
├── ...existing fields...
└── github_token_encrypted: String (nullable) — Fernet-encrypted GitHub PAT
```

New environment variable: `REPO_ENCRYPTION_KEY` — Fernet symmetric key for encrypting stored tokens.

### New/Modified API Endpoints
| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| POST | `/api/repos` | Yes | `{ url: string, github_token?: string }` | Repo object (token NOT returned) |
| PATCH | `/api/repos/:id` | Yes | `{ github_token?: string }` | Repo object |
| GET | `/api/scans/:id/sarif` | Yes | — | SARIF v2.1.0 JSON |

### SARIF v2.1.0 Mapping
```
Finding.severity → SARIF result.level:
  critical, high → "error"
  medium → "warning"
  low, informational → "note"

Finding.vulnerability_type → SARIF result.ruleId (slugified, e.g. "sql-injection")
Finding.file_path + line_number → SARIF result.locations[0].physicalLocation
Finding.description → SARIF result.message.text
Finding.explanation → SARIF result.properties.explanation (custom property)
```

## Coding Standards
- Python: snake_case files, async handlers, `[Security]` prefix for token operations
- TypeScript: same patterns as core phases
- Never log or return decrypted tokens

## Deliverables

1. **Alembic migration** — add `github_token_encrypted` column to repositories
2. **`backend/app/services/crypto_service.py`** — Fernet encrypt/decrypt for tokens
3. **`backend/app/schemas/repo.py`** (extend) — add optional `github_token` to CreateRepoRequest
4. **`backend/app/routers/repos.py`** (extend) — accept and encrypt token on create/update
5. **`backend/app/scanner/git_ops.py`** (extend) — use token in clone URL for private repos
6. **`backend/app/services/sarif_service.py`** — generate SARIF JSON from scan findings
7. **`backend/app/routers/scans.py`** (extend) — add `GET /:id/sarif` endpoint
8. **`frontend/app/dashboard/page.tsx`** (extend) — add optional token field to "Add Repository" form
9. **`frontend/app/scans/[id]/page.tsx`** (extend) — add "Export SARIF" button

## Technical Specification

### backend/app/services/crypto_service.py
- Uses `cryptography.fernet.Fernet`
- `encrypt_token(plaintext: str) -> str`: encrypt with `REPO_ENCRYPTION_KEY`, return base64 string
- `decrypt_token(ciphertext: str) -> str`: decrypt and return plaintext
- Key loaded from `settings.repo_encryption_key`
- If key not configured, raise `ValueError("REPO_ENCRYPTION_KEY not set")`

### backend/app/scanner/git_ops.py (extend)
- `clone_repo(url: str, dest: Path, github_token: str | None = None) -> str`:
  - If `github_token` provided and URL is `https://github.com/...`:
    - Rewrite URL: `https://{github_token}@github.com/{owner}/{repo}.git`
  - Log: `[Scanner] Cloning {url} (authenticated: {bool(github_token)})` — never log the token itself

### backend/app/services/sarif_service.py
- `generate_sarif(scan, findings) -> dict`:
  - SARIF v2.1.0 schema
  - `$schema`: `"https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"`
  - `version`: `"2.1.0"`
  - `runs[0].tool.driver.name`: `"ZeroPath Security Scanner"`
  - `runs[0].tool.driver.version`: `"1.0.0"`
  - `runs[0].tool.driver.rules`: array of unique rules derived from distinct `vulnerability_type` values
  - `runs[0].results`: array of finding results mapped per the SARIF mapping above

### Frontend Changes
- Dashboard "Add Repository" form: add collapsible "Advanced" section with optional "GitHub Token" password input and help text: "Required for private repositories. Your token is encrypted at rest."
- Scan detail page: add "Export SARIF" button next to scan header. On click: fetch `GET /api/scans/:id/sarif`, trigger download as `zeropath-scan-{scan_id}.sarif.json`.

## Acceptance Criteria

1. Creating a repo with a valid GitHub token encrypts and stores it
2. Token is never returned in any API response (write-only field)
3. Cloning a private repo with valid token succeeds
4. Cloning a private repo without token fails with clear error message
5. Invalid/expired tokens produce a clear error in scan failure message
6. `GET /api/scans/:id/sarif` returns valid SARIF v2.1.0 JSON
7. SARIF output contains correct rules, results, and physical locations
8. "Export SARIF" button triggers file download
9. Dashboard form has optional token field in "Advanced" section
10. `REPO_ENCRYPTION_KEY` missing → clear error on startup
