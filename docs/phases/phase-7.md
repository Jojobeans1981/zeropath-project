# Phase 7: README, Tests & Polish

## Objective
Write the comprehensive README (a graded deliverable), add backend tests, polish the frontend UX, and prepare deployment configuration.

## Current State (After Phase 6)
- **Backend:** Complete API: auth (4), repos (3), scans (POST, GET/:id, GET/:id/findings, GET/compare), findings (GET/:id, PATCH/:id/triage). Full scanner pipeline with Celery. Triage carry-forward. Cross-scan comparison.
- **Frontend:** Complete UI: login/signup, dashboard, repo detail (scan history + new scan + compare links), scan detail (polling + findings + filter bar + comparison), FindingCard (expandable + triage), ComparisonTable, SeverityBadge, StatusBadge, NavHeader.
- **Database:** SQLite with 5 tables: users, repositories, scans, findings, triage_statuses.
- **All core features functional end-to-end.**

## Deliverables

1. **`README.md`** — comprehensive project documentation (graded deliverable)
2. **`backend/tests/conftest.py`** — test fixtures (async DB, client, auth)
3. **`backend/tests/test_auth.py`** — auth endpoint tests
4. **`backend/tests/test_scans.py`** — scan endpoint tests
5. **`backend/tests/test_scanner.py`** — scanner component unit tests
6. **Frontend polish** — loading/error/empty states, responsive layout
7. **NavHeader update** — user email + logout button
8. **Deployment config** — Vercel (frontend) + Railway (backend)

## Technical Specification

### README.md (project root)

The README is a graded deliverable. It must cover every topic from the ZeroPath spec's "README as a Deliverable" section. Structure:

```markdown
# ZeroPath Security Scanner

One-paragraph description of what this is.

## Quick Start
Prerequisites, env vars, four terminal commands to run locally.

## Architecture Overview
ASCII diagram (copy from PRD Section 4.2).
Explanation of component responsibilities:
- FastAPI backend (REST API)
- Celery worker (background scan processing)
- Redis (task broker)
- SQLite (persistence)
- Next.js frontend (dashboard UI)

## Prompt Design
- System prompt: establishes senior security auditor role, lists 15+ vulnerability classes, instructs JSON-only output, emphasizes "only genuine vulnerabilities"
- User prompt: presents code with file paths and line numbers, specifies exact JSON schema for each finding
- Why this approach: single prompt per chunk covers all vuln classes (vs. per-class prompts which are N× more expensive). Explicit JSON schema instruction achieves ~95% compliance with Claude Sonnet. "Do not invent issues" instruction reduces false positives.
- Example: show a redacted version of the system and user prompts

## LLM Output Parsing
- Primary: `json.loads()` on the full response text
- Fallback: regex extraction of JSON array (`\[[\s\S]*\]`) for cases where LLM wraps JSON in markdown or adds commentary
- Validation: each finding checked for required fields, correct severity enum, positive line_number. Invalid findings are logged and discarded, not surfaced.
- Why not tool use: structured prompts achieve similar reliability with less API complexity and easier iteration

## Token & Context Window Management
- Estimation: ~4 characters per token (conservative heuristic)
- Chunk size: 80K tokens per chunk, leaving ~120K for system prompt + response in Claude's 200K context window
- File integrity: never split a file across chunks. If a single file exceeds 80K tokens, truncate with [TRUNCATED] marker.
- Priority ordering: files with security-relevant names (auth, config, db, api, etc.) are scanned first with maximum context
- Why file-level grouping: preserves intra-file data flow (most vulnerabilities are within a single file). Function-level chunking would miss cross-function flows; sliding windows waste tokens on overlap.

## Finding Identity & Stability
- Identity hash: SHA-256 of `{vuln_type}::{file_path}::{normalized_5_line_context}`
- Normalization: strip whitespace, remove comment-only lines, lowercase
- Why content-based: line numbers are too fragile (any insertion shifts them). AST analysis is complex and breaks on syntax errors. Content hashing tolerates formatting changes and line shifts.
- Triage carry-forward: new scan findings automatically inherit triage status from prior scan findings with matching identity_hash
- Known limitation: substantially rewritten code produces new identity hashes (by design — rewritten code deserves fresh review)

## What I Chose Not to Build (and Why)
- Private repo auth: credential management is significant scope; public repos demonstrate the scanner
- WebSocket updates: 5-second polling is indistinguishable from real-time for 2-5 minute scans
- RBAC: single-user scoping via user_id is sufficient; roles add complexity without demonstrating scanner capability
- CI/CD webhooks: the API supports programmatic scan creation; webhook infrastructure is integration work, not scanner work
- SARIF export: straightforward serialization task; prioritized triage and comparison instead
- Auto-remediation: second LLM pass per finding doubles cost; triage workflow is more immediately useful

## What I'd Build Next (Given Another Week)
1. Private repo support (GitHub OAuth or token-based clone)
2. Parallel chunk analysis (process chunks concurrently, not sequentially)
3. SARIF export for GitHub Code Scanning integration
4. WebSocket updates for real-time scan progress
5. Finding confidence scores (based on LLM certainty signals)
6. Multi-language support (JavaScript/TypeScript)

## Known Limitations
- SQLite: single-writer concurrency. Fine for single-user, would need PostgreSQL for production.
- Sequential chunk analysis: chunks are processed one at a time. Parallel processing would cut scan time.
- Shallow clone only: scans HEAD, not full history. Historical analysis would need full clone.
- Public repos only: no authentication for private repositories.
- No rate limiting: API endpoints are unprotected against abuse.
- Token estimation: 4 chars/token is a rough heuristic, not a tokenizer.

## API Reference
Link to FastAPI auto-generated docs at /docs when running locally.

## Tech Stack
Table of all dependencies with versions and rationale.
```

**Important:** The README should be honest about limitations. Don't oversell. Demonstrate product thinking by explaining tradeoffs, not just features.

### backend/tests/conftest.py

```python
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.database import Base, get_db

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def auth_client(client):
    # Create a user and return authenticated client
    signup_res = await client.post("/api/auth/signup", json={
        "email": "test@example.com",
        "password": "testpass123"
    })
    token = signup_res.json()["data"]["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
```

### backend/tests/test_auth.py
- `test_signup_success`: POST /api/auth/signup → 200, response has access_token and refresh_token
- `test_signup_duplicate_email`: signup twice with same email → second returns 409
- `test_login_success`: signup then login → 200 with tokens
- `test_login_wrong_password`: signup then login with wrong password → 401
- `test_me_authenticated`: signup, use token, GET /api/auth/me → 200 with user data
- `test_me_unauthenticated`: GET /api/auth/me without token → 401
- `test_refresh_token`: signup, use refresh_token in POST /api/auth/refresh → 200 with new access_token

### backend/tests/test_scans.py
- `test_create_scan`: create repo, POST /api/scans → 200, status is "queued"
- `test_create_scan_invalid_repo`: POST /api/scans with fake repo_id → 404
- `test_get_scan`: create scan, GET /api/scans/:id → 200 with scan data
- Note: these tests mock the Celery task (`scan_worker.run_scan.delay`) to avoid actual LLM calls. Use `unittest.mock.patch`.

### backend/tests/test_scanner.py
- `test_chunker_single_file`: one small file → one chunk
- `test_chunker_multiple_files`: several files totaling > 80K tokens → multiple chunks
- `test_chunker_oversized_file`: one file > 80K tokens → truncated with marker
- `test_chunker_priority_ordering`: files with "auth" in name come before "utils"
- `test_dedup_stable_hash`: same inputs → same hash
- `test_dedup_different_vuln_type`: same code, different vuln_type → different hash
- `test_dedup_tolerates_whitespace`: code with added spaces → same hash (after normalization)
- `test_parser_valid_json`: valid JSON array → parsed correctly
- `test_parser_json_in_markdown`: JSON wrapped in ```json``` → extracted and parsed
- `test_parser_empty_array`: `"[]"` → empty list
- `test_parser_malformed`: garbage text → empty list (graceful failure)

### Frontend Polish

**All pages must have three states:**

1. **Loading state**: skeleton placeholders with `animate-pulse`. At least 2-3 skeleton items matching the expected content shape.

2. **Error state**: centered card with red icon, error message, and "Try Again" button that re-fetches.

3. **Empty state**: centered message with helpful text and action prompt. Examples:
   - Dashboard empty: "No repositories yet. Add a Git repository URL above to get started."
   - Repo detail no scans: "No scans yet. Click 'New Scan' to analyze this repository."
   - Scan complete no findings: "No vulnerabilities found. This codebase passed the security scan." (with green check icon)

**Pages to verify/update:**
- `/dashboard` — loading, error, empty repos
- `/repos/[id]` — loading, error, empty scans
- `/scans/[id]` — loading, error, empty findings

### NavHeader Update

Modify `frontend/app/components/NavHeader.tsx`:
- Fetch current user on mount: `GET /api/auth/me` (cache in state)
- Right side: show user email, then a "Logout" button
- Logout: call `clearTokens()`, `router.push("/login")`
- If no token (shouldn't happen, but defensive): show nothing on right side

### Deployment Configuration

**Frontend (Vercel):**
- `frontend/vercel.json` (if needed) or configure via Vercel dashboard
- Environment variable: `NEXT_PUBLIC_API_URL` → set to Railway backend URL
- No special config needed — Next.js deploys to Vercel out of the box

**Backend (Railway):**
- `backend/Procfile`:
  ```
  web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
  worker: celery -A app.workers.scan_worker worker --loglevel=info
  ```
- Railway supports multiple processes from a single repo via Procfile
- Environment variables: all from `.env.example`, plus `PORT` (auto-set by Railway)
- Redis: add Railway managed Redis add-on, set `REDIS_URL` to the provided URL
- Database: SQLite works on Railway's persistent volume. Document that PostgreSQL is recommended for production.

**Document deployment steps in README:**
1. Fork repo
2. Connect to Vercel (frontend directory)
3. Connect to Railway (backend directory)
4. Add Redis add-on on Railway
5. Set environment variables
6. Deploy

## Acceptance Criteria

1. README covers every topic from the ZeroPath spec's "README as a Deliverable" section
2. README includes architecture diagram, prompt design explanation, output parsing strategy, token management, finding stability, what wasn't built (with reasoning), what to build next, known limitations
3. `cd backend && pytest` passes all tests (auth, scans, scanner components)
4. All pages have loading, error, and empty states
5. NavHeader shows user email and functional logout button
6. Full E2E flow works: signup → add repo → scan → view findings → triage → compare scans
7. Responsive layout: single column on mobile, max-w-4xl on desktop
8. `backend/Procfile` exists for Railway deployment
9. README includes local setup and deployment instructions
