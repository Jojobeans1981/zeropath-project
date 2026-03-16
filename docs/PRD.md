# ZeroPath Security Scanner — Product Requirements Document

## 1. Executive Summary

ZeroPath is a web application that enables AppSec engineers to submit Python Git repositories for LLM-powered security analysis, view structured vulnerability findings, and manage remediation through a triage workflow. It replaces the fragmented process of running static analysis tools, reading terminal output, and tracking fixes in spreadsheets — with a single authenticated dashboard that scans, surfaces, and tracks security vulnerabilities across repository versions.

**Core value proposition:** Centralized, LLM-powered Python security scanning with finding persistence, deduplication, and triage — purpose-built for AppSec workflows.

---

## 2. Goals & Success Metrics

### Primary Goals
- Accept any public Git repo URL containing Python code and produce structured security findings via LLM analysis
- Provide an authenticated dashboard with scan submission, status tracking, and results viewing
- Enable triage workflow (open / false positive / resolved) with notes per finding
- Support scan history per repo with cross-scan comparison (new, fixed, persisting findings)
- Deduplicate findings across scans using stable identity hashing

### Measurable Success Criteria
- A submitted repo scan completes and returns structured findings within 5 minutes for repos under 50 files
- Findings include severity, vulnerability type, file path, line number, description, and LLM explanation
- Cross-scan comparison correctly identifies new, fixed, and persisting findings
- REST API is fully separated from the frontend — all data flows through API endpoints
- README covers architecture, prompt design, LLM output parsing, token management, and finding stability

### Out of Scope (Core Delivery)
These items are excluded from Phases 0–7 but addressed in stretch phases 8–11:
- Private repo authentication (SSH keys, GitHub tokens) → Phase 8
- SARIF report export → Phase 8
- Real-time WebSocket scan updates → Phase 9
- Role-based access control → Phase 10
- CI/CD integration / webhook triggers → Phase 10
- Auto-remediation / LLM fix suggestions → Phase 11
- Multi-language support beyond Python → Phase 11

---

## 3. User Stories & Personas

### Persona: AppSec Engineer (Primary)
An application security engineer responsible for identifying and triaging vulnerabilities across internal Python services. Needs faster feedback than manual code review and more contextual findings than traditional SAST tools.

### User Stories

| Priority | Story |
|----------|-------|
| P0 | As an AppSec engineer, I want to sign up and log in so that my scans and triage state persist across sessions |
| P0 | As an AppSec engineer, I want to submit a Git repo URL and kick off a scan so that I can analyze a codebase without cloning it locally |
| P0 | As an AppSec engineer, I want to see structured findings (severity, vuln type, file, line, description, explanation) so that I can quickly assess risk |
| P0 | As an AppSec engineer, I want to see scan status (queued, running, complete, failed) so that I know when results are ready |
| P0 | As an AppSec engineer, I want to mark findings as open, false positive, or resolved with optional notes so that I can track triage progress |
| P1 | As an AppSec engineer, I want to see scan history per repo and compare across scans so that I can track whether vulnerabilities are new, fixed, or persisting |
| P1 | As an AppSec engineer, I want findings to be deduplicated across scans so that the same vulnerability isn't reported as new every time |
| P1 | As an AppSec engineer, I want the API to be cleanly separated from the frontend so that I can integrate with other tools later |
| P2 | As an AppSec engineer, I want a comprehensive README explaining architecture decisions, prompt design, and tradeoffs so that I can evaluate the engineering approach |

---

## 4. Technical Architecture

### 4.1 Stack & Dependencies

**Backend (Python)**
| Dependency | Version | Why |
|-----------|---------|-----|
| FastAPI | ^0.115 | Async-first Python web framework, excellent for background tasks and OpenAPI docs |
| Uvicorn | ^0.34 | ASGI server for FastAPI |
| SQLAlchemy | ^2.0 | ORM with async support, mature migration ecosystem |
| Alembic | ^1.14 | Database migrations for SQLAlchemy |
| SQLite (aiosqlite) | — | Zero-config database, sufficient for single-node deployment |
| python-jose[cryptography] | ^3.3 | JWT token generation and validation |
| passlib[bcrypt] | ^1.7 | Password hashing |
| GitPython | ^3.1 | Clone and traverse Git repositories |
| anthropic | ^0.52 | Claude API client for LLM-powered analysis |
| pydantic | ^2.0 | Request/response validation (bundled with FastAPI) |
| pydantic-settings | ^2.0 | Environment variable loading |
| celery | ^5.4 | Task queue for background scan processing |
| redis | ^5.0 | Celery broker and result backend |
| httpx | ^0.28 | Async HTTP client for testing |
| pytest | ^8.0 | Testing framework |
| pytest-asyncio | ^0.24 | Async test support |

**Frontend (TypeScript)**
| Dependency | Version | Why |
|-----------|---------|-----|
| Next.js | ^14.2 | React framework with App Router, matches user's existing stack |
| React | ^18 | UI library |
| Tailwind CSS | ^3.4 | Utility-first CSS, matches user's existing approach |
| @heroicons/react | ^2.2 | Icon library, already used in user's projects |

### 4.2 System Architecture

```
┌─────────────────────────────────────┐
│           Next.js Frontend          │
│  (App Router, Tailwind, TypeScript) │
│                                     │
│  /login  /signup  /dashboard        │
│  /scans/[id]  /repos/[id]          │
└──────────────┬──────────────────────┘
               │ REST API calls
               ▼
┌─────────────────────────────────────┐
│         FastAPI Backend             │
│                                     │
│  /api/auth/*     - Auth endpoints   │
│  /api/repos/*    - Repo management  │
│  /api/scans/*    - Scan CRUD + run  │
│  /api/findings/* - Findings + triage│
└──────┬──────────────┬───────────────┘
       │              │
       ▼              ▼
┌────────────┐  ┌───────────────┐
│  SQLite DB │  │ Celery + Redis │
│            │  │ (Task Queue)   │
│ users      │  └───────┬───────┘
│ repos      │          │
│ scans      │          ▼
│ findings   │  ┌───────────────┐
│ triage     │  │  Scan Worker   │
└────────────┘  │                │
                │ 1. git clone   │
                │ 2. discover .py│
                │ 3. chunk files │
                │ 4. LLM analyze │
                │ 5. parse output│
                │ 6. deduplicate │
                │ 7. save to DB  │
                └───────┬───────┘
                        │
                        ▼
                ┌───────────────┐
                │  Claude API   │
                │ (Sonnet 4)    │
                └───────────────┘
```

**Deployment (Stretch — Phase 7):**
- Frontend: Vercel
- Backend + Worker: Railway or Render
- Redis: Railway managed Redis or Render Redis
- Database: SQLite on Railway persistent volume (or upgrade to PostgreSQL)

### 4.3 Data Models

```
User
├── id: UUID (PK)
├── email: string (unique, indexed)
├── password_hash: string
├── created_at: datetime
└── updated_at: datetime

Repository
├── id: UUID (PK)
├── user_id: UUID (FK → User)
├── url: string
├── name: string (extracted from URL, e.g. "owner/repo")
├── created_at: datetime
├── updated_at: datetime
└── UNIQUE(user_id, url)

Scan
├── id: UUID (PK)
├── repo_id: UUID (FK → Repository)
├── status: enum(queued, running, complete, failed)
├── commit_sha: string (nullable, resolved at clone time)
├── error_message: string (nullable)
├── files_scanned: int (default 0)
├── started_at: datetime (nullable)
├── completed_at: datetime (nullable)
├── created_at: datetime
└── updated_at: datetime

Finding
├── id: UUID (PK)
├── scan_id: UUID (FK → Scan)
├── identity_hash: string (indexed, for dedup — hash of vuln_type + file_path + normalized_context)
├── severity: enum(critical, high, medium, low, informational)
├── vulnerability_type: string (e.g. "SQL Injection", "Path Traversal")
├── file_path: string
├── line_number: int
├── code_snippet: string
├── description: string
├── explanation: string (LLM-generated detailed explanation)
├── created_at: datetime
└── updated_at: datetime

TriageStatus
├── id: UUID (PK)
├── finding_id: UUID (FK → Finding, unique together with user_id)
├── user_id: UUID (FK → User)
├── status: enum(open, false_positive, resolved)
├── notes: string (nullable)
├── created_at: datetime
└── updated_at: datetime
```

**Finding Identity & Deduplication Strategy:**
- `identity_hash` = SHA-256 of `f"{vulnerability_type}::{file_path}::{normalized_code_context}"`
- "Normalized code context" = ~5 lines around the vulnerable line, stripped of whitespace and comments, lowercased
- Cross-scan comparison: compare `identity_hash` sets between two scans to derive new/fixed/persisting
- Triage carry-forward: when a new scan produces a finding with a matching hash from a prior scan of the same repo, the triage status is automatically copied to the new finding

### 4.4 API Surface

**Auth**
| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/api/auth/signup` | `{ email, password }` | `{ access_token, refresh_token, token_type }` |
| POST | `/api/auth/login` | `{ email, password }` | `{ access_token, refresh_token, token_type }` |
| POST | `/api/auth/refresh` | `{ refresh_token }` | `{ access_token, token_type }` |
| GET | `/api/auth/me` | — | `{ id, email, created_at }` |

**Repositories**
| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/api/repos` | `{ url }` | Repo object (creates or returns existing) |
| GET | `/api/repos` | — | Array of user's repos with `scan_count` |
| GET | `/api/repos/:id` | — | Repo detail with scan history |

**Scans**
| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/api/scans` | `{ repo_id }` | Scan object (status: queued) |
| GET | `/api/scans/:id` | — | Scan detail with status |
| GET | `/api/scans/:id/findings` | `?severity=&triage_status=` | Array of findings (filterable) |
| GET | `/api/scans/compare` | `?base=:id&head=:id` | `{ new[], fixed[], persisting[], counts }` |

**Findings & Triage**
| Method | Path | Request | Response |
|--------|------|---------|----------|
| GET | `/api/findings/:id` | — | Finding detail with triage status |
| PATCH | `/api/findings/:id/triage` | `{ status, notes? }` | Updated triage status |

**Auth model:** JWT Bearer tokens. Access token (30 min TTL), refresh token (7 day TTL). All endpoints except signup/login require `Authorization: Bearer <token>`.

**Response envelope (all endpoints):**
```json
// Success
{ "success": true, "data": { ... } }

// Error
{ "success": false, "error": { "code": "SCAN_NOT_FOUND", "message": "No scan found with the given ID." } }
```

### 4.5 File Structure

```
zeropath/
├── README.md
├── docs/
│   ├── PRD.md
│   ├── phases/
│   └── prompts/
│
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app, CORS, lifespan
│   │   ├── config.py                # Pydantic Settings, env vars
│   │   ├── database.py              # SQLAlchemy async engine + session
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── repository.py
│   │   │   ├── scan.py
│   │   │   ├── finding.py
│   │   │   └── triage.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── repo.py
│   │   │   ├── scan.py
│   │   │   └── finding.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── repos.py
│   │   │   ├── scans.py
│   │   │   └── findings.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── repo_service.py
│   │   │   ├── scan_service.py
│   │   │   └── finding_service.py
│   │   ├── scanner/
│   │   │   ├── __init__.py
│   │   │   ├── git_ops.py           # Clone, discover .py files
│   │   │   ├── chunker.py           # File chunking for context windows
│   │   │   ├── prompts.py           # LLM prompt templates
│   │   │   ├── analyzer.py          # LLM API calls, output parsing
│   │   │   └── dedup.py             # Identity hashing, deduplication
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   └── scan_worker.py       # Celery task
│   │   └── deps.py                  # Dependency injection (auth, db)
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_scans.py
│       └── test_scanner.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs
│   ├── tailwind.config.js
│   ├── postcss.config.mjs
│   ├── lib/
│   │   ├── api.ts                   # Centralized apiFetch wrapper
│   │   └── auth.ts                  # Token management (localStorage)
│   └── app/
│       ├── layout.tsx
│       ├── page.tsx                  # Redirect to /dashboard or /login
│       ├── globals.css
│       ├── components/
│       │   ├── NavHeader.tsx
│       │   ├── SeverityBadge.tsx
│       │   ├── StatusBadge.tsx
│       │   ├── FindingCard.tsx
│       │   └── ComparisonTable.tsx
│       ├── login/
│       │   └── page.tsx
│       ├── signup/
│       │   └── page.tsx
│       ├── dashboard/
│       │   └── page.tsx
│       ├── repos/
│       │   └── [id]/
│       │       └── page.tsx
│       └── scans/
│           └── [id]/
│               └── page.tsx
│
└── docker-compose.yml               # Redis service
```

---

## 5. Coding Standards (Project-Specific)

### Python Backend
- **Framework:** FastAPI with `Depends()` injection, Pydantic models for all request/response schemas
- **File naming:** lowercase snake_case (`scan_service.py`, `auth.py`)
- **Class naming:** PascalCase for models and services
- **Functions:** `async def` for all route handlers and database operations
- **Error handling:** Raise `HTTPException` with structured error codes; wrap in `{ success, error }` envelope
- **Logging:** `[Stage]` prefixed messages (e.g. `[Scanner] Analyzing chunk 2/5`)
- **Comments:** Minimal — explain WHY not WHAT
- **Config:** Environment variables via `pydantic-settings`, never hardcoded secrets

### TypeScript Frontend
Derived from user's existing Tributary project:
- **Directives:** `"use client"` on all interactive pages
- **Types:** Interfaces defined at top of file, no `any` types
- **State:** `useState` for local state, no global state library
- **Data fetching:** Centralized `apiFetch<T>()` wrapper returning `{ success, data?, error? }`
- **Auth:** Token storage in `localStorage` via `getAccessToken()`, `setTokens()`, `clearTokens()`
- **Loading:** Skeleton states with `animate-pulse` placeholder divs
- **Styling:** Tailwind utility classes, custom color palette
- **Exports:** Named exports for components, default exports for pages
- **Auth guard:** `useEffect` checks for token, redirects to `/login` if missing
- **Error display:** Local state strings, rendered below forms or in alert boxes

### Anti-Patterns to Avoid
- No `any` types in TypeScript
- No prop drilling beyond one level
- No nested ternaries
- No inline styles
- No hardcoded API URLs (use `NEXT_PUBLIC_API_URL` env var)
- No synchronous database calls in Python
- No storing raw passwords

---

## 6. Implementation Phases

### Phase 0: Project Scaffolding

**Objective:** Set up the monorepo structure, install dependencies, configure dev tooling, verify both servers run — zero business logic.

**Prerequisites:** Node.js >= 18, Python >= 3.11, Redis (Docker or local), Anthropic API key.

**Deliverables:**
1. Backend: FastAPI app returning `{ "status": "ok" }` at `GET /api/health`
2. Frontend: Next.js app rendering a placeholder page at `http://localhost:3000`
3. `docker-compose.yml` with Redis service
4. SQLAlchemy async engine + Alembic migration config (empty schema)
5. Celery worker connecting to Redis, processing a no-op test task
6. `apiFetch<T>()` wrapper and `auth.ts` utilities in frontend
7. `.env.example` documenting all required environment variables
8. `.gitignore` for Python, Node, and environment files

**Acceptance Criteria:**
- `uvicorn app.main:app --reload` starts and `/api/health` returns 200
- `npm run dev` starts and renders at localhost:3000
- `docker compose up redis` starts Redis on port 6379
- `celery -A app.workers.scan_worker worker` starts without errors
- `alembic revision --autogenerate` works
- `.env.example` lists: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `JWT_SECRET`, `REDIS_URL`, `CORS_ORIGINS`

---

### Phase 1: Authentication System

**Objective:** Implement user signup, login, JWT tokens, and protected routes — the foundation for user-scoped data.

**Prerequisites:** Phase 0 complete.

**Deliverables:**
1. User model + Alembic migration
2. `POST /api/auth/signup` — create account, return tokens
3. `POST /api/auth/login` — validate credentials, return tokens
4. `POST /api/auth/refresh` — issue new access token from refresh token
5. `GET /api/auth/me` — return current user profile
6. `get_current_user` dependency for protecting routes
7. Frontend login page (`/login`)
8. Frontend signup page (`/signup`)
9. Root page (`/`) redirects to `/dashboard` if authenticated, `/login` if not

**Technical Details:**
- User model: `id` (UUID), `email` (unique indexed), `password_hash`, `created_at`, `updated_at`
- Password hashing: `passlib` with bcrypt scheme
- JWT: `python-jose` with HS256, access token 30 min TTL, refresh token 7 day TTL
- Token payload: `{ "sub": "<user_id>", "exp": <timestamp> }`
- Pydantic schemas: `SignupRequest(email, password)`, `LoginRequest(email, password)`, `TokenResponse(access_token, refresh_token, token_type)`, `UserResponse(id, email, created_at)`

**Acceptance Criteria:**
- Signup creates user and returns valid tokens
- Signup with duplicate email returns 409
- Login with wrong password returns 401
- `/api/auth/me` returns user data with valid token, 401 without
- Refresh endpoint issues new access token from valid refresh token
- Frontend forms work end-to-end (signup → redirect, login → redirect)
- Navigating to `/dashboard` without token redirects to `/login`

---

### Phase 2: Repository Management & Git Operations

**Objective:** Users can submit Git repo URLs, persist them, and the system can clone repos and discover Python files.

**Prerequisites:** Phase 1 complete.

**Deliverables:**
1. Repository model + Alembic migration
2. `POST /api/repos` — create or return existing repo for the user
3. `GET /api/repos` — list user's repos with scan count
4. `GET /api/repos/:id` — repo detail (must belong to current user)
5. `scanner/git_ops.py` — shallow clone + Python file discovery
6. Frontend dashboard (`/dashboard`) — repo list + "Add Repository" form
7. Frontend repo detail (`/repos/[id]`) — repo info, placeholder for scan history

**Technical Details:**
- Repository model: `id` (UUID), `user_id` (FK→User), `url`, `name` (extracted as `owner/repo` from URL), `created_at`, `updated_at`. Unique on `(user_id, url)`.
- `clone_repo(url: str, dest: Path) -> str`: Shallow clone (`git clone --depth=1`), returns HEAD commit SHA. Timeout: 60 seconds.
- `discover_python_files(repo_path: Path) -> list[Path]`: Walk directory tree, yield `.py` files, skip: `.git`, `venv`, `env`, `.venv`, `node_modules`, `__pycache__`, `.tox`, `.eggs`, `site-packages`.
- Clone destination: configurable via `SCAN_WORKDIR` env var, defaults to `/tmp/zeropath-scans/`
- URL validation: must match `https://github.com/` or `https://gitlab.com/` pattern (extensible)

**Acceptance Criteria:**
- POST `/api/repos` with valid GitHub URL creates repo and returns it
- POST `/api/repos` with same URL for same user returns existing repo (idempotent)
- GET `/api/repos` returns only the current user's repos
- `clone_repo()` clones a public GitHub repo and returns commit SHA
- `discover_python_files()` returns `.py` files, excludes venvs and caches
- Dashboard lists repos and allows adding new ones
- Repo detail page renders repo info

---

### Phase 3: LLM-Powered Scanner Engine

**Objective:** Build the core scanning pipeline: chunk files, prompt Claude, parse findings, compute identity hashes, persist results — all as a Celery background task.

**Prerequisites:** Phase 2 complete, `ANTHROPIC_API_KEY` configured.

**Deliverables:**
1. Scan model + Finding model + Alembic migration
2. `scanner/chunker.py` — group files into ~80K token chunks
3. `scanner/prompts.py` — system and user prompt templates
4. `scanner/analyzer.py` — call Claude API, parse JSON output
5. `scanner/dedup.py` — compute identity hash per finding
6. `workers/scan_worker.py` — Celery task orchestrating the full pipeline
7. `POST /api/scans` — create scan, enqueue Celery task
8. `GET /api/scans/:id` — return scan status and metadata

**Technical Details:**

*Chunker (`scanner/chunker.py`):*
- `chunk_files(files: list[FileContent], max_tokens: int = 80000) -> list[Chunk]`
- Token estimate: 1 token ≈ 4 characters
- Never split a file across chunks; if a single file exceeds `max_tokens`, truncate it with a `[TRUNCATED]` marker
- Priority ordering: files matching security-relevant patterns first: `auth`, `login`, `api`, `route`, `view`, `model`, `admin`, `settings`, `config`, `db`, `sql`, `query`, `middleware`, `password`, `token`, `session`, `permission`
- Each `Chunk` contains: list of `{ file_path, content, start_line, end_line }`

*Prompts (`scanner/prompts.py`):*
- System prompt: establishes the role as a senior security auditor specializing in Python. Instructs to find vulnerabilities across all classes: SQL injection, command injection, path traversal, SSRF, XSS, insecure deserialization, hardcoded secrets/credentials, broken authentication, IDOR, race conditions, unsafe regex, weak cryptography, information disclosure.
- User prompt: presents code with file paths and line numbers. Specifies JSON output format.
- Output format instruction: return a JSON array where each element has: `severity` (critical/high/medium/low/informational), `vulnerability_type` (string), `file_path` (string), `line_number` (int), `code_snippet` (string, the vulnerable line(s)), `description` (one sentence summary), `explanation` (2-4 sentence detailed explanation with remediation hint).
- Instruction: return `[]` if no vulnerabilities found. Do not invent issues — only report genuine vulnerabilities.

*Analyzer (`scanner/analyzer.py`):*
- Model: `claude-sonnet-4-20250514`
- Parse JSON from Claude's response: first try `json.loads()` on the full response, then try extracting JSON array via regex `\[[\s\S]*\]` if first attempt fails
- Validate each finding: all required fields present, severity is a valid enum value, line_number is a positive integer
- Discard findings that fail validation (log a warning)
- Retry once on API error (rate limit, timeout) with 5-second backoff

*Dedup (`scanner/dedup.py`):*
- `compute_identity_hash(vuln_type: str, file_path: str, file_content: str, line_number: int) -> str`
- Extract ~5 lines of context: lines `max(1, line_number-2)` through `line_number+2`
- Normalize: strip leading/trailing whitespace per line, remove lines that are only comments (`#`), lowercase everything
- Hash: SHA-256 of `f"{vuln_type}::{file_path}::{normalized_context}"`

*Celery Worker (`workers/scan_worker.py`):*
- Task `run_scan(scan_id: str)`:
  1. Set status → `running`, record `started_at`
  2. Clone repo via `git_ops.clone_repo()`
  3. Discover Python files via `git_ops.discover_python_files()`
  4. Chunk files via `chunker.chunk_files()`
  5. For each chunk: `analyzer.analyze_chunk()`, collect raw findings
  6. Compute `identity_hash` for each finding via `dedup.compute_identity_hash()`
  7. Deduplicate within scan (same hash → keep first occurrence)
  8. Persist findings to database
  9. Set status → `complete`, record `files_scanned`, `completed_at`
  10. On any unrecoverable error: set status → `failed`, record `error_message`
  11. Always clean up cloned repo in `finally` block

**Acceptance Criteria:**
- POST `/api/scans` creates scan with status `queued` and enqueues task
- Worker progresses scan: queued → running → complete (or failed)
- GET `/api/scans/:id` reflects current status
- Findings have all required fields populated
- Each finding has a deterministic `identity_hash`
- Files over 80K tokens are chunked correctly
- Single oversized files are truncated, not dropped
- Failed clone or API error → status `failed` with error message
- Cloned repo directory is cleaned up even on failure

---

### Phase 4: Findings Dashboard & Scan Results UI

**Objective:** Build the frontend for viewing scan results: trigger scans, poll for status, display findings with full detail.

**Prerequisites:** Phase 3 complete.

**Deliverables:**
1. `GET /api/scans/:id/findings` — findings list (filterable by severity)
2. `GET /api/findings/:id` — finding detail
3. Updated repo detail page with scan history and "New Scan" button
4. Scan detail page (`/scans/[id]`) with status polling and findings list
5. `SeverityBadge` component — color-coded severity indicator
6. `StatusBadge` component — scan status indicator
7. `FindingCard` component — expandable card for individual findings

**Technical Details:**
- Repo detail page: list scans ordered newest first, each showing status badge, date, finding count. "New Scan" button calls POST `/api/scans`.
- Scan detail page: header shows status, commit SHA, files scanned, timestamps. While `queued` or `running`: poll GET `/api/scans/:id` every 5 seconds via `useEffect` + `setInterval`, clear on unmount or terminal status. When `complete`: render findings. When `failed`: show error message.
- Severity badge colors: critical → red bg, high → orange bg, medium → yellow bg, low → blue bg, informational → gray bg
- Status badge: queued → gray, running → blue + `animate-pulse`, complete → green, failed → red
- FindingCard: shows severity badge, vulnerability type, `file_path:line_number`, description (truncated to 2 lines). Expands on click to show full explanation and code snippet in a monospace block.
- Empty state: "No vulnerabilities found" with a check icon when scan is complete with zero findings.

**Acceptance Criteria:**
- Repo detail shows scan history ordered by date
- "New Scan" button creates scan and navigates to scan detail
- Scan detail polls and updates status in real-time
- Findings render with all fields once scan completes
- Severity badges are correctly color-coded
- Failed scans show error message
- Zero-finding scans show empty state message
- Expanding a finding card shows full explanation and code snippet

---

### Phase 5: Triage Workflow

**Objective:** Enable users to mark findings as open, false positive, or resolved with optional notes.

**Prerequisites:** Phase 4 complete.

**Deliverables:**
1. TriageStatus model + Alembic migration
2. `PATCH /api/findings/:id/triage` — create or update triage status
3. Triage carry-forward logic in scan worker
4. Triage controls in FindingCard (status dropdown + notes + save)
5. Filter bar on scan page (filter by triage status and severity)

**Technical Details:**
- TriageStatus model: `id` (UUID), `finding_id` (FK→Finding), `user_id` (FK→User), `status` (open/false_positive/resolved), `notes` (nullable text), `created_at`, `updated_at`. Unique on `(finding_id, user_id)`.
- PATCH endpoint: upserts triage record for the current user + finding
- `carry_forward_triage(scan_id, user_id)`: for each finding in the new scan, look up the most recent finding with the same `identity_hash` in prior scans of the same repo. If found and triaged, copy the triage status and notes to a new TriageStatus record for the new finding.
- Call `carry_forward_triage()` at end of scan worker pipeline, after findings are persisted.
- FindingCard extension: dropdown (`select`) for status (Open / False Positive / Resolved), textarea for notes (shown when card is expanded), save button. Show current triage status as a small colored badge next to severity.
- Filter bar: horizontal row of pill-style toggles. Two groups: triage status (All / Open / False Positive / Resolved) and severity (All / Critical / High / Medium / Low / Info). Client-side filtering.

**Acceptance Criteria:**
- PATCH `/api/findings/:id/triage` saves status and notes
- Finding cards display and allow editing of triage status
- Filter bar filters findings by triage status and severity
- New scan findings inherit triage from prior scan findings with same identity_hash
- Changing triage on one scan's finding does NOT retroactively affect prior scans

---

### Phase 6: Cross-Scan Comparison

**Objective:** Compare two scans of the same repo to show new, fixed, and persisting findings.

**Prerequisites:** Phase 5 complete.

**Deliverables:**
1. `GET /api/scans/compare?base=:id&head=:id` — comparison endpoint
2. Comparison logic using identity_hash set operations
3. `ComparisonTable` component — three sections for new/fixed/persisting
4. Comparison UI on scan detail page (dropdown to select comparison scan)
5. "Compare" links between consecutive scans on repo detail page

**Technical Details:**
- `compare_scans(base_scan_id, head_scan_id) -> ComparisonResult`:
  - Validate both scans belong to the same repo, both are `complete`
  - Get identity_hash sets for each scan
  - `new` = hashes in head but not in base → return findings from head scan
  - `fixed` = hashes in base but not in head → return findings from base scan
  - `persisting` = hashes in both → return findings from head scan
- Response includes `counts: { new: int, fixed: int, persisting: int }` plus finding arrays
- ComparisonTable: three collapsible sections — "New Findings" (red left border), "Fixed Findings" (green left border), "Persisting Findings" (gray left border). Each section shows count in header and lists FindingCard components.
- Scan detail page: "Compare with..." dropdown listing other completed scans of the same repo, sorted newest first. Selecting a scan fetches comparison.
- Repo detail page: between consecutive completed scans, show a small "Compare ↔" link.

**Acceptance Criteria:**
- Comparison API correctly categorizes findings as new/fixed/persisting
- Self-comparison returns all as persisting, none as new/fixed
- Cross-repo comparison returns validation error
- Non-complete scan comparison returns validation error
- Comparison UI renders three labeled, color-coded sections
- Compare dropdown on scan page works
- Compare links on repo page work

---

### Phase 7: README, Tests & Polish

**Objective:** Write the comprehensive README (a graded deliverable), add tests, polish UX, and prepare deployment config.

**Prerequisites:** Phase 6 complete.

**Deliverables:**
1. `README.md` covering all required topics from the ZeroPath spec
2. Backend tests: auth, scan creation, scanner components (chunker, dedup, parser)
3. Frontend polish: loading/error/empty states on all pages, responsive layout
4. NavHeader: user email display + logout button
5. Deployment configuration for Vercel (frontend) + Railway (backend/worker/Redis)

**README Must Cover:**
1. Architecture overview with diagram
2. How to run locally (prerequisites, env vars, start commands)
3. Prompt design: system prompt role, user prompt structure, JSON output format, example vuln classes
4. LLM output parsing: JSON parse → regex fallback → field validation → discard malformed
5. Token/context window management: 4 chars/token estimate, 80K chunks, file integrity, priority ordering, truncation
6. Finding identity and stability: identity_hash = SHA-256(vuln_type::file_path::normalized_context), 5-line window, normalization, triage carry-forward
7. What was not built and why (with reasoning for each)
8. What to build next given another week
9. Known limitations and deliberate shortcuts

**Tests:**
- `tests/conftest.py`: async test DB (in-memory SQLite), `httpx.AsyncClient` fixture, authenticated client fixture
- `tests/test_auth.py`: signup success + duplicate email, login success + wrong password, /me endpoint, token refresh
- `tests/test_scans.py`: create scan, get scan status, get findings (mock Celery task to avoid actual LLM calls)
- `tests/test_scanner.py`: chunker groups files correctly and respects token limit, dedup produces stable hashes for same input, parser handles valid JSON + malformed JSON + empty array

**Polish:**
- Every page: loading skeleton, error state with message, empty state with helpful text
- NavHeader: display user email, logout button (clears tokens, redirects to `/login`)
- Responsive: single column on mobile, `max-w-4xl` on desktop
- Form validation: inline errors, disabled submit while loading

**Deployment Config:**
- `frontend/vercel.json` or `next.config.mjs` env rewrites for API URL
- `backend/Procfile` or `railway.toml` for Railway: web process (uvicorn) + worker process (celery)
- Document deployment steps in README

**Acceptance Criteria:**
- README covers every topic from the spec's "README as a Deliverable" section
- `pytest` passes all tests
- All pages have loading, error, and empty states
- Full E2E flow: signup → add repo → scan → view findings → triage → compare
- NavHeader shows email + logout works
- Responsive on mobile widths
- Deployment config files present and documented

---

### Phase 8 (Stretch): Private Repo Auth + SARIF Export

**Objective:** Support scanning private GitHub repos via personal access tokens, and export findings in SARIF format.

**Prerequisites:** Phase 7 complete.

**Deliverables:**
1. GitHub token storage per repo (encrypted in DB)
2. Modified `git_ops.clone_repo()` to use token-authenticated HTTPS URLs
3. UI for entering/managing GitHub token when adding a repo
4. `GET /api/scans/:id/sarif` — export findings as SARIF v2.1.0 JSON
5. "Export SARIF" button on scan detail page

**Technical Details:**
- Add `github_token` (nullable, encrypted) field to Repository model. Encrypt with Fernet symmetric encryption using a `REPO_ENCRYPTION_KEY` env var.
- When cloning, if `github_token` is present, rewrite URL: `https://{token}@github.com/{owner}/{repo}.git`
- SARIF output: follow SARIF v2.1.0 schema. Map: Finding.severity → SARIF `level` (error/warning/note), Finding.vulnerability_type → SARIF `ruleId`, Finding.file_path + line_number → SARIF `physicalLocation`.
- "Add Repository" form: optional "GitHub Token" field with password input type and help text explaining it's needed for private repos only.

**Acceptance Criteria:**
- Private repos clone successfully with a valid token
- Invalid/expired tokens produce a clear error message
- Tokens are never returned in API responses (write-only)
- SARIF export produces valid SARIF v2.1.0 JSON
- SARIF file can be uploaded to GitHub Code Scanning (manual verification)

---

### Phase 9 (Stretch): WebSocket Real-Time Updates

**Objective:** Replace polling with WebSocket connections for live scan status and finding streaming.

**Prerequisites:** Phase 7 complete.

**Deliverables:**
1. WebSocket endpoint: `WS /api/ws/scans/:id`
2. Scan worker publishes progress events to Redis pub/sub
3. Backend relays Redis events through WebSocket to connected clients
4. Frontend scan detail page connects via WebSocket instead of polling
5. Progressive finding display (findings appear as they're discovered, not all at once)

**Technical Details:**
- FastAPI `WebSocket` route at `/api/ws/scans/{scan_id}`. Authenticate via query param: `?token=<access_token>`.
- Worker publishes to Redis channel `scan:{scan_id}:events`. Event types: `status_change` (status, timestamp), `chunk_progress` (chunk_index, total_chunks), `finding_discovered` (finding data), `scan_complete` (summary).
- Backend WebSocket handler: subscribe to Redis channel, forward events as JSON to client. Close connection on scan completion.
- Frontend: `useEffect` opens WebSocket, receives events, updates state. Falls back to polling if WebSocket connection fails.

**Acceptance Criteria:**
- WebSocket connects with valid token, rejects invalid token
- Scan progress events arrive in real-time (no 5-second delay)
- Findings appear progressively as chunks are analyzed
- Connection closes cleanly on scan completion
- Falls back to polling if WebSocket fails

---

### Phase 10 (Stretch): RBAC + CI/CD Webhooks

**Objective:** Add role-based access control and GitHub webhook integration for automated scanning.

**Prerequisites:** Phase 7 complete.

**Deliverables:**
1. User roles: `admin`, `member`, `viewer`
2. Role-based permissions on all endpoints
3. `POST /api/webhooks/github` — receive push events and trigger scans
4. GitHub webhook signature verification (`X-Hub-Signature-256`)
5. Admin UI for managing team members and roles

**Technical Details:**
- Add `role` field to User model (default: `member`). Permissions: `viewer` (read scans/findings only), `member` (full CRUD, triage), `admin` (manage users, view all repos/scans).
- `get_current_user` dependency extended with optional `required_role` parameter.
- Webhook endpoint: verify `X-Hub-Signature-256` header using a `GITHUB_WEBHOOK_SECRET` env var. On `push` event to default branch: find matching repo by URL, create scan, enqueue task.
- Admin page (`/admin`): list users, change roles, invite users (sends email — or just displays invite link for v1).

**Acceptance Criteria:**
- Viewers cannot create scans or update triage
- Members can do everything except manage users
- Admins can manage roles
- GitHub webhook triggers scan on push to default branch
- Invalid webhook signatures are rejected with 403
- Admin UI allows role management

---

### Phase 11 (Stretch): Auto-Remediation + Multi-Language

**Objective:** Generate LLM-powered fix suggestions for findings, and extend file discovery to JavaScript/TypeScript.

**Prerequisites:** Phase 7 complete.

**Deliverables:**
1. `POST /api/findings/:id/remediation` — generate fix suggestion via LLM
2. Remediation prompt template in `scanner/prompts.py`
3. Remediation display in FindingCard (code diff view)
4. Extended file discovery: `.js`, `.ts`, `.jsx`, `.tsx` files
5. Language-aware prompt selection (Python vs JavaScript system prompts)

**Technical Details:**
- Remediation: second LLM call with the finding's code_snippet, description, and surrounding file context. Prompt instructs Claude to return a JSON object: `{ "fixed_code": "...", "explanation": "...", "confidence": "high|medium|low" }`.
- Cache remediation results in a new `Remediation` model (finding_id FK, fixed_code, explanation, confidence, created_at). Don't regenerate if already cached.
- Display: show original code vs fixed code side-by-side in FindingCard expansion. Color-code: removed lines red, added lines green.
- Multi-language: `discover_source_files(repo_path, languages=["python"])` replaces `discover_python_files()`. Accepts list of language keys, each mapping to file extensions and excluded directories.
- Language-specific system prompts in `prompts.py`: `SYSTEM_PROMPTS = { "python": "...", "javascript": "..." }`.
- Add `language` field to Finding model.

**Acceptance Criteria:**
- Remediation endpoint returns fix suggestion with confidence score
- Remediation is cached — second call for same finding returns cached result
- Fix suggestions display as a code diff in the UI
- JavaScript/TypeScript files are discovered and scanned when enabled
- Findings include correct language label
- Python and JavaScript prompts are appropriately specialized

---

## 7. Risk Register

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| LLM returns malformed/non-JSON output | H | M | Regex fallback parser, field validation, discard incomplete findings |
| LLM hallucinates vulnerabilities (false positives) | M | H | Prompt constraints ("only genuine vulnerabilities"), triage workflow for human review |
| Large repos exceed context window limits | H | M | 80K token chunking, file priority ordering, truncation with marker |
| Anthropic API rate limits or outages | H | L | Retry with 5s backoff, scan marked as failed with clear message |
| Identity hash instability across code changes | M | M | 5-line normalized context window, ignore whitespace/comments |
| SQLite write contention under concurrent scans | M | L | Acceptable for take-home; document as known limitation |
| Git clone fails (repo deleted, private, network) | M | L | 60s timeout, clear error message, scan marked as failed |
| Scope creep beyond core phases | H | M | Stretch phases are explicitly optional and independent |
| Deployment platform differences vs local dev | M | M | Docker Compose for local parity; Railway/Vercel config in Phase 7 |

---

## 8. Dependencies & Environment

### Required Services
| Service | Purpose | Required |
|---------|---------|----------|
| Anthropic API | LLM-powered code analysis | Yes |
| Redis | Celery task broker | Yes |
| Vercel | Frontend hosting (stretch) | Phase 7+ |
| Railway/Render | Backend + worker hosting (stretch) | Phase 7+ |

### Environment Variable Manifest

```bash
# Backend
DATABASE_URL=sqlite+aiosqlite:///./zeropath.db
ANTHROPIC_API_KEY=sk-ant-...
JWT_SECRET=<random-32-char-string>
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379/0
SCAN_WORKDIR=/tmp/zeropath-scans
CORS_ORIGINS=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000

# Stretch (Phase 8)
REPO_ENCRYPTION_KEY=<fernet-key>

# Stretch (Phase 10)
GITHUB_WEBHOOK_SECRET=<random-string>
```

### Running Locally
```bash
# Terminal 1: Redis
docker compose up redis

# Terminal 2: Backend
cd backend && pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery Worker
cd backend && celery -A app.workers.scan_worker worker --loglevel=info

# Terminal 4: Frontend
cd frontend && npm install && npm run dev
```

---

## Appendix A: Technical Decisions Summary

### Decision 1: Backend Framework — FastAPI over Django/Flask/Express

**Chosen:** FastAPI

| Alternative | Why rejected |
|-------------|-------------|
| Django + DRF | Synchronous by default, heavy for API-only backend, admin panel not needed |
| Flask | No native async, no built-in validation or API docs |
| Express.js | Spec requires Python backend |

**Rationale:** Native async is critical for I/O-bound work (LLM API calls, git clone). Pydantic validation and auto-generated OpenAPI docs are built-in.

### Decision 2: Database — SQLite over PostgreSQL

**Chosen:** SQLite via aiosqlite

| Alternative | Why rejected |
|-------------|-------------|
| PostgreSQL | Adds setup friction for evaluators; can migrate later via SQLAlchemy abstraction |
| MongoDB | Data is relational (scans→findings→triage); document store would denormalize awkwardly |

**Rationale:** Zero-config for evaluators. SQLAlchemy abstracts the engine — migrating to Postgres is a one-line config change.

### Decision 3: Task Queue — Celery + Redis

**Chosen:** Celery with Redis broker

| Alternative | Why rejected |
|-------------|-------------|
| FastAPI BackgroundTasks | No persistence — server restart loses running tasks, no retry |
| Dramatiq | Smaller community, marginal complexity difference |
| ARQ | Less mature, poor Windows support |

**Rationale:** Industry standard with retry, persistence, and monitoring. Scans are long-running (2-5 min) and can fail mid-flight.

### Decision 4: LLM — Claude Sonnet over Opus/GPT-4o/local

**Chosen:** claude-sonnet-4-20250514

| Alternative | Why rejected |
|-------------|-------------|
| Claude Opus | 5x cost, slower — overkill for file-level scanning |
| GPT-4o | Competitive but ZeroPath is Anthropic-ecosystem |
| Local models | Much weaker security reasoning, harder evaluator setup |

**Rationale:** Best cost/quality ratio for code analysis. 200K context window. Strong structured output compliance.

### Decision 5: Frontend — Next.js 14 over Vite/SvelteKit

**Chosen:** Next.js 14 App Router

| Alternative | Why rejected |
|-------------|-------------|
| Vite + React | No file-based routing, less structure for multi-page dashboard |
| SvelteKit | Less familiar to evaluators, smaller component ecosystem |

**Rationale:** File-based routing matches the multi-page dashboard structure. Matches user's existing Tributary project patterns.

### Decision 6: Finding Identity — Content Hash over line numbers/AST

**Chosen:** SHA-256 of `vuln_type::file_path::normalized_5_line_context`

| Alternative | Why rejected |
|-------------|-------------|
| Line number + file path | Breaks on any code insertion above the vulnerable line |
| AST node identity | Requires Python parser, complex, breaks on syntax errors |
| LLM-generated ID | Non-deterministic across runs |

**Rationale:** Tolerates line shifts, deterministic, simple to implement. 5-line normalized context is specific enough for identity but resilient to minor edits.

### Decision 7: Chunking — File-level groups over function-level

**Chosen:** Group whole files into ~80K token chunks

| Alternative | Why rejected |
|-------------|-------------|
| Function-level | Loses cross-function data flow context, requires AST parsing |
| Sliding window | Token-wasteful overlap, boundary dedup needed |
| Whole-repo single prompt | Most repos exceed 200K tokens |
| File-by-file API calls | 200 files = 200 calls = 30+ minutes |

**Rationale:** Preserves intra-file data flow. Priority ordering scans security-relevant files first. 80K limit leaves headroom in Claude's 200K window.

### Decision 8: Auth — JWT over session cookies

**Chosen:** JWT Bearer tokens (access + refresh)

| Alternative | Why rejected |
|-------------|-------------|
| Session cookies | CSRF complexity, ties to browser clients, requires server-side storage |
| OAuth2 (Auth0/Clerk) | External dependency evaluators would need accounts for |

**Rationale:** Stateless, works naturally with API-first architecture. 30-min access token limits exposure window.

### Decision 9: API Response Format — Wrapped envelope

**Chosen:** `{ success: boolean, data?: T, error?: { code, message } }`

| Alternative | Why rejected |
|-------------|-------------|
| Raw data + HTTP codes | Inconsistent error body shapes across status codes |
| GraphQL | Over-engineered for simple CRUD access patterns |

**Rationale:** One `apiFetch` wrapper handles all cases. Machine-readable error codes + human-readable messages. Matches existing Tributary project conventions.

### Decision 10: Deployment — Vercel + Railway

**Chosen:** Frontend on Vercel, backend + worker + Redis on Railway

| Alternative | Why rejected |
|-------------|-------------|
| Local only | Doesn't demonstrate production readiness |
| Docker Compose full stack | More setup friction for evaluators, no managed services |

**Rationale:** Vercel is the standard for Next.js deployment. Railway supports multiple processes (web + worker) with managed Redis, matching our Celery architecture.
