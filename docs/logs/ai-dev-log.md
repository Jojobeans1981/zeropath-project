# AI Dev Log

Records what was built by AI in each session, including decisions made and deviations from spec.

## 2026-03-16 — Phase 0: Project Scaffolding

- Created root config: `.gitignore`, `.env.example`, `docker-compose.yml`
- Scaffolded backend: FastAPI app, SQLAlchemy async DB, Alembic, Celery config, config/settings
- Scaffolded frontend: Next.js 14, Tailwind CSS, `apiFetch` utility, auth token helpers
- **Deviation:** Had to fix Alembic `env.py` to add `import app.models` so autogenerate could discover models
- **Env issue:** Node v24 too new for Next.js 14 — user switched to Node 20 LTS

## 2026-03-16 — Phase 1: Authentication System

- Created User model with UUID PK, email, password_hash, timestamps
- Created auth schemas (Pydantic): SignupRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse
- Created auth_service: bcrypt hashing, JWT encode/decode via python-jose
- Created auth router: POST /signup, POST /login, POST /refresh, GET /me
- Updated deps.py with `get_current_user` (OAuth2 bearer + DB lookup)
- Created frontend login and signup pages with client-side validation
- Updated root page.tsx to redirect based on auth state
- **Fix:** Pinned `bcrypt==4.0.1` for passlib compatibility (bcrypt 5.x breaks passlib's version detection)
- **Fix:** Pinned `greenlet==3.0.3` for Python 3.9 on Windows (latest greenlet fails to compile)
- All 6 backend verification checks passed

## 2026-03-16 — Phase 2: Repository Management & Git Operations

- Created Repository model with user FK, unique constraint on (user_id, url)
- Created repo schemas, service (CRUD with graceful Scan model fallback), and router
- Created git_ops module: shallow clone + Python file discovery with directory skipping
- Created frontend: NavHeader component, dashboard page (repo list + add form), repo detail page
- **Fix:** `str | None` syntax not supported in Python 3.9 — changed to `Optional[str]`
- **Fix:** `@/*` tsconfig path maps to `./app/*`, so imports use `@/components/` not `@/app/components/`
- All backend endpoints verified, frontend TypeScript clean

## 2026-03-16 — Phase 3: LLM-Powered Scanner Engine

- Created Scan model (status, commit_sha, files_scanned, timestamps) and Finding model (severity, vuln_type, file_path, line_number, code_snippet, description, explanation, identity_hash)
- Created scan schemas (Pydantic with Optional for Python 3.9), scan_service, and scans router
- Created scanner modules: chunker (token-based file grouping with security-relevance prioritization), prompts (system + user templates), dedup (SHA-256 identity hash from code context window)
- Created analyzer module: calls Claude Sonnet API, parses JSON response, validates findings, retries on rate limit
- Created full Celery scan pipeline: clone → discover → chunk → analyze → dedup → persist, with error handling and temp dir cleanup
- **Fix:** `get_scan` lazy-loaded `scan.repo` in async context causing MissingGreenlet error — switched to `selectinload(Scan.repo)` eager loading
- **Fix:** Used `from __future__ import annotations` and `List` from typing for Python 3.9 compat in chunker dataclasses
- POST /api/scans creates queued scan — verified
- GET /api/scans/:id returns scan with status — verified

## 2026-03-16 — Phase 4: Findings Dashboard & Scan Results UI

- Created finding_service with severity-sorted listing and ownership verification via eager loading
- Added GET /api/scans/:id/findings endpoint with optional severity filter
- Created GET /api/findings/:id endpoint for individual finding detail
- Extended GET /api/repos/:id to return scans array (RepoDetailResponse)
- Created frontend components: SeverityBadge, StatusBadge, FindingCard (expandable with code snippet)
- Created scan detail page with 5-second polling during queued/running states, severity summary badges
- Rewrote repo detail page with scan history list and "New Scan" button
- **Pattern:** Used `selectinload` consistently for all async relationship access to avoid MissingGreenlet
- All API endpoints verified, frontend TypeScript clean

## 2026-03-16 — Phase 5: Triage Workflow

- Created TriageStatus model with unique constraint per finding+user, migration applied
- Extended FindingResponse with triage_status/triage_notes fields
- Created PATCH /api/findings/:id/triage endpoint with upsert pattern
- Updated get_findings_for_scan to outer-join TriageStatus for current user
- Added carry_forward_triage sync function (called in Celery worker, best-effort)
- Extended FindingCard with triage badge (Open/FP/Resolved), status buttons, notes textarea, save
- Added filter bar to scan detail page: triage filter (All/Open/FP/Resolved) + severity filter (All/Critical/High/Medium/Low/Info)
- Client-side filtering with combined triage AND severity filters
- All triage endpoints verified, frontend TypeScript clean

## 2026-03-16 — Phase 6: Cross-Scan Comparison

- Added ComparisonResponse, ComparisonCounts schemas to scan.py
- Created compare_scans service: set operations on identity_hash (new/fixed/persisting), includes triage data
- Added GET /api/scans/compare?base=X&head=Y endpoint (placed before /{scan_id} to avoid route conflict)
- Created ComparisonTable component with collapsible sections (red=new, green=fixed, gray=persisting)
- Extended scan detail: comparison dropdown, auto-trigger via ?compare= query param, clear comparison button
- Extended repo detail: "Compare" links between consecutive complete scans
- All backend verified, frontend TypeScript clean

## 2026-03-16 — Phase 7: README, Tests & Polish

- Created test suite: conftest.py (in-memory SQLite, async fixtures, auth_client), test_auth (7 tests), test_scans (2 tests with mocked Celery), test_scanner (14 unit tests for chunker/dedup/parser/validator)
- **Fix:** Test POST to /api/repos needed trailing slash, mock path was `app.workers.scan_worker.run_scan` not `app.services.scan_service.run_scan`
- 23/23 tests pass
- Created comprehensive README: architecture diagram, prompt design, parsing strategy, token management, identity hashing, trade-offs, limitations, API reference, tech stack
- Updated NavHeader: fetches user email via GET /me, shows logout button, redirects on expired token
- Created deployment config: Procfile (web + worker), runtime.txt (Python 3.11), startup auto-migration
- Added `port` setting to config.py

## 2026-03-16 — Phase 8: Private Repo Auth + SARIF Export

- Created crypto_service (Fernet encrypt/decrypt) for GitHub token storage
- Added github_token_encrypted column to Repository model + migration
- Updated repo creation to accept optional github_token (write-only, encrypted at rest)
- Updated Celery worker to decrypt token for authenticated clones
- Created SARIF v2.1.0 export service with proper schema, rules dedup, severity mapping
- Added GET /api/scans/:id/sarif endpoint (before /{scan_id} to avoid route conflict)
- Frontend: collapsible "Advanced" section with password input for GitHub token
- Frontend: "Export SARIF" button triggers file download via Blob
- 23/23 tests still pass, frontend TypeScript clean

## 2026-03-16 — Phase 9: WebSocket Real-Time Updates

- Created pubsub_service: sync publisher (Celery worker) + async subscriber (WebSocket handler) via Redis pub/sub
- Created WebSocket endpoint at /api/ws/scans/{scan_id} with token auth via query param
- Auth: validates JWT, verifies scan ownership, closes with custom codes (4001/4003/4004)
- Terminal scans send one event then close immediately
- Added event publishing to worker: status_change, chunk_progress, finding_discovered, scan_complete, scan_failed (all best-effort)
- Frontend: WebSocket with polling fallback, progress bar showing chunk N of M, progressive findings during scan
- On scan_complete, does final fetchScan() to get accurate triage data
- 23/23 tests pass, frontend TypeScript clean
