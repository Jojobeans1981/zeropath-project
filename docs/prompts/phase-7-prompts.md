# Phase 7: README, Tests & Polish — Implementation Prompts

## Prompt 7.1 — Backend Test Suite

```
ROLE: You are writing the backend test suite for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/main.py` — FastAPI app with all routers (auth, repos, scans, findings)
- `backend/app/database.py` — Base, get_db(), async engine
- `backend/app/models/` — User, Repository, Scan, Finding, TriageStatus
- `backend/app/services/auth_service.py` — hash_password, verify_password, create_access_token, create_refresh_token, decode_token
- `backend/app/scanner/chunker.py` — FileContent, Chunk, chunk_files, prioritize_files
- `backend/app/scanner/dedup.py` — compute_identity_hash
- `backend/app/scanner/analyzer.py` — parse_llm_response, validate_finding
- `backend/tests/__init__.py` — empty
- pytest and pytest-asyncio in requirements.txt

TASK:
Create test fixtures and comprehensive tests.

CREATE:

1. `backend/tests/conftest.py`:
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
       await engine.dispose()


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
       res = await client.post("/api/auth/signup", json={
           "email": "test@example.com",
           "password": "testpass123",
       })
       data = res.json()
       token = data["data"]["access_token"]
       client.headers["Authorization"] = f"Bearer {token}"
       return client
   ```

2. `backend/tests/test_auth.py`:
   ```python
   import pytest


   @pytest.mark.asyncio
   async def test_signup_success(client):
       res = await client.post("/api/auth/signup", json={
           "email": "new@example.com",
           "password": "password123",
       })
       assert res.status_code == 200
       data = res.json()
       assert data["success"] is True
       assert "access_token" in data["data"]
       assert "refresh_token" in data["data"]


   @pytest.mark.asyncio
   async def test_signup_duplicate_email(client):
       await client.post("/api/auth/signup", json={
           "email": "dup@example.com",
           "password": "password123",
       })
       res = await client.post("/api/auth/signup", json={
           "email": "dup@example.com",
           "password": "password456",
       })
       assert res.status_code == 409


   @pytest.mark.asyncio
   async def test_login_success(client):
       await client.post("/api/auth/signup", json={
           "email": "login@example.com",
           "password": "password123",
       })
       res = await client.post("/api/auth/login", json={
           "email": "login@example.com",
           "password": "password123",
       })
       assert res.status_code == 200
       assert res.json()["data"]["access_token"]


   @pytest.mark.asyncio
   async def test_login_wrong_password(client):
       await client.post("/api/auth/signup", json={
           "email": "wrong@example.com",
           "password": "password123",
       })
       res = await client.post("/api/auth/login", json={
           "email": "wrong@example.com",
           "password": "wrongpass",
       })
       assert res.status_code == 401


   @pytest.mark.asyncio
   async def test_me_authenticated(auth_client):
       res = await auth_client.get("/api/auth/me")
       assert res.status_code == 200
       assert res.json()["data"]["email"] == "test@example.com"


   @pytest.mark.asyncio
   async def test_me_unauthenticated(client):
       res = await client.get("/api/auth/me")
       assert res.status_code == 401


   @pytest.mark.asyncio
   async def test_refresh_token(client):
       signup_res = await client.post("/api/auth/signup", json={
           "email": "refresh@example.com",
           "password": "password123",
       })
       refresh_token = signup_res.json()["data"]["refresh_token"]
       res = await client.post("/api/auth/refresh", json={
           "refresh_token": refresh_token,
       })
       assert res.status_code == 200
       assert res.json()["data"]["access_token"]
   ```

3. `backend/tests/test_scans.py`:
   ```python
   import pytest
   from unittest.mock import patch


   @pytest.mark.asyncio
   async def test_create_scan(auth_client):
       # Create a repo first
       repo_res = await auth_client.post("/api/repos", json={
           "url": "https://github.com/pallets/flask",
       })
       repo_id = repo_res.json()["data"]["id"]

       with patch("app.services.scan_service.run_scan") as mock_task:
           mock_task.delay = lambda x: None
           res = await auth_client.post("/api/scans", json={
               "repo_id": repo_id,
           })
       assert res.status_code == 200
       assert res.json()["data"]["status"] == "queued"


   @pytest.mark.asyncio
   async def test_create_scan_invalid_repo(auth_client):
       with patch("app.services.scan_service.run_scan") as mock_task:
           mock_task.delay = lambda x: None
           res = await auth_client.post("/api/scans", json={
               "repo_id": "00000000-0000-0000-0000-000000000000",
           })
       assert res.status_code == 404
   ```

4. `backend/tests/test_scanner.py`:
   ```python
   from app.scanner.chunker import FileContent, chunk_files, prioritize_files
   from app.scanner.dedup import compute_identity_hash
   from app.scanner.analyzer import parse_llm_response, validate_finding


   def test_chunker_single_file():
       files = [FileContent(path="app.py", content="x = 1\n" * 100, line_count=100)]
       chunks = chunk_files(files, max_tokens=80000)
       assert len(chunks) == 1
       assert len(chunks[0].files) == 1


   def test_chunker_multiple_chunks():
       # Create files that exceed one chunk
       big_content = "x = 1\n" * 100000  # ~600K chars = ~150K tokens
       files = [FileContent(path=f"file{i}.py", content=big_content, line_count=100000) for i in range(3)]
       chunks = chunk_files(files, max_tokens=80000)
       assert len(chunks) >= 3


   def test_chunker_oversized_file():
       huge = "x = 1\n" * 500000  # Way over 80K tokens
       files = [FileContent(path="huge.py", content=huge, line_count=500000)]
       chunks = chunk_files(files, max_tokens=80000)
       assert len(chunks) == 1
       assert "[TRUNCATED" in chunks[0].files[0].content


   def test_chunker_priority_ordering():
       files = [
           FileContent(path="utils.py", content="x=1", line_count=1),
           FileContent(path="auth.py", content="x=1", line_count=1),
           FileContent(path="helpers.py", content="x=1", line_count=1),
       ]
       prioritized = prioritize_files(files)
       assert prioritized[0].path == "auth.py"


   def test_dedup_stable_hash():
       h1 = compute_identity_hash("SQL Injection", "app.py", "line1\nline2\nline3\nline4\nline5", 3)
       h2 = compute_identity_hash("SQL Injection", "app.py", "line1\nline2\nline3\nline4\nline5", 3)
       assert h1 == h2


   def test_dedup_different_vuln_type():
       h1 = compute_identity_hash("SQL Injection", "app.py", "code", 1)
       h2 = compute_identity_hash("XSS", "app.py", "code", 1)
       assert h1 != h2


   def test_dedup_tolerates_whitespace():
       h1 = compute_identity_hash("SQLi", "a.py", "  x = 1  \n  y = 2  ", 1)
       h2 = compute_identity_hash("SQLi", "a.py", "x = 1\ny = 2", 1)
       assert h1 == h2


   def test_parser_valid_json():
       result = parse_llm_response('[{"severity": "high", "vulnerability_type": "XSS"}]')
       assert len(result) == 1


   def test_parser_json_in_markdown():
       result = parse_llm_response('```json\n[{"severity": "high"}]\n```')
       assert len(result) == 1


   def test_parser_empty_array():
       result = parse_llm_response("[]")
       assert result == []


   def test_parser_malformed():
       result = parse_llm_response("this is not json at all")
       assert result == []


   def test_validate_finding_valid():
       f = {
           "severity": "high",
           "vulnerability_type": "SQLi",
           "file_path": "app.py",
           "line_number": 10,
           "code_snippet": "code",
           "description": "desc",
           "explanation": "expl",
       }
       assert validate_finding(f) is True


   def test_validate_finding_missing_keys():
       assert validate_finding({"severity": "high"}) is False


   def test_validate_finding_bad_severity():
       f = {
           "severity": "super_critical",
           "vulnerability_type": "SQLi",
           "file_path": "a.py",
           "line_number": 1,
           "code_snippet": "c",
           "description": "d",
           "explanation": "e",
       }
       assert validate_finding(f) is False
   ```

CODING STYLE:
- pytest-asyncio for async tests
- unittest.mock.patch for mocking Celery tasks
- Plain functions (not async) for scanner unit tests
- Each test is independent (no shared state)

CONSTRAINTS:
- Tests use in-memory SQLite, not the real DB
- Celery tasks are mocked (no Redis needed for tests)
- Do NOT test the actual LLM calls (that requires API key)
```

## Prompt 7.2 — README

```
ROLE: You are writing the comprehensive README for ZeroPath Security Scanner — this is a graded deliverable.

CONTEXT:
The project is a complete LLM-powered Python security scanner with:
- FastAPI backend, Celery + Redis worker, SQLite database
- Next.js 14 frontend with TypeScript + Tailwind CSS
- Claude Sonnet for code analysis
- Features: auth, repo management, LLM scanning, triage workflow, cross-scan comparison
- Deployment: Vercel (frontend) + Railway (backend)

TASK:
Create README.md at the project root covering every topic from the ZeroPath spec's "README as a Deliverable" section. Be honest about limitations. Demonstrate product thinking.

CREATE `README.md` in the project root with these sections:

1. **Title + one-paragraph description**
2. **Quick Start** — prerequisites, env setup, 4-5 terminal commands
3. **Architecture Overview** — ASCII diagram showing: Browser → Next.js → FastAPI REST API → SQLite, FastAPI → Celery Worker → Claude API, Celery ↔ Redis
4. **Prompt Design** — system prompt strategy (senior auditor role, 15+ vuln classes, JSON-only output), user prompt format (file sections with line numbers, exact JSON schema), why single-prompt-per-chunk approach
5. **LLM Output Parsing** — primary json.loads, regex fallback for markdown wrapping, per-finding validation, graceful degradation
6. **Token & Context Window Management** — 4 chars/token estimation, 80K token chunks, file-level integrity, security-priority ordering, why file-level grouping (not function-level or sliding window)
7. **Finding Identity & Stability** — SHA-256 of vuln_type + file_path + normalized 5-line context, normalization rules, why content-based (not line-number), triage carry-forward mechanism, known limitations
8. **What I Chose Not to Build** — each item with explicit reasoning
9. **What I'd Build Next** — prioritized list with rationale
10. **Known Limitations** — honest list
11. **API Reference** — link to FastAPI /docs
12. **Tech Stack** — table with all deps, versions, rationale

CODING STYLE for the README:
- Conversational but professional
- Show don't tell — include code snippets for prompt design and parsing
- Honest about shortcuts (SQLite, no rate limiting, etc.)
- Architecture diagram in ASCII (not mermaid — more portable)

CONSTRAINTS:
- Do NOT oversell — acknowledge limitations clearly
- The README should stand alone (someone with no context should understand the project)
- Include redacted versions of prompts (not full prompts, but enough to show the approach)
```

## Prompt 7.3 — Frontend Polish + NavHeader Update

```
ROLE: You are polishing the frontend UX for ZeroPath Security Scanner.

CONTEXT:
The frontend has these pages:
- `/login` and `/signup` — auth pages
- `/dashboard` — repo list + add form
- `/repos/[id]` — repo detail with scan history
- `/scans/[id]` — scan detail with findings, triage, comparison

Components: NavHeader, SeverityBadge, StatusBadge, FindingCard, ComparisonTable

TASK:
Polish all pages to have consistent loading/error/empty states, and complete the NavHeader.

MODIFY pages to ensure three states each:

1. **Loading state**: skeleton placeholders with `animate-pulse bg-gray-200 rounded` matching content shape
2. **Error state**: centered card with red icon, error message, "Try Again" button
3. **Empty state**: centered text with helpful action prompt

Specific fixes:
- `/dashboard`: loading skeletons (3 cards), error card, empty state with callout
- `/repos/[id]`: loading skeleton, error card, empty scans state
- `/scans/[id]`: loading skeleton, error card, empty findings state (green "No vulnerabilities found")

MODIFY `frontend/app/components/NavHeader.tsx`:
- On mount: call `GET /api/auth/me` to get user email
- Right side: show user email + "Logout" button
- Logout handler: call `clearTokens()`, `router.push("/login")`
- Cache user data in state to avoid re-fetching on every page
- If API call fails (expired token): call clearTokens, redirect to /login

Add responsive layout tweaks:
- All page containers: `max-w-4xl mx-auto px-4 py-8`
- Cards: full-width on mobile, consistent padding
- Form inputs: full-width with proper spacing

CODING STYLE:
- Consistent error component pattern across all pages
- Loading skeletons match the shape of the actual content
- Responsive: single column, max-w-4xl centered

CONSTRAINTS:
- Do NOT add new features — only polish existing ones
- Keep all existing functionality intact
```

## Prompt 7.4 — Deployment Configuration

```
ROLE: You are configuring deployment for ZeroPath Security Scanner.

CONTEXT:
- Backend: FastAPI + Celery worker, needs Redis, uses SQLite
- Frontend: Next.js 14

TASK:
Create deployment configuration files.

CREATE:

1. `backend/Procfile`:
   ```
   web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
   worker: celery -A app.workers.scan_worker worker --loglevel=info --concurrency=2
   ```

2. `backend/runtime.txt`:
   ```
   python-3.11.11
   ```

3. MODIFY `backend/app/config.py` — add optional PORT:
   ```python
   port: int = 8000
   ```

4. MODIFY `backend/app/main.py` — add startup event for Alembic auto-migration in production:
   ```python
   @app.on_event("startup")
   async def startup():
       """Run migrations on startup (for Railway deployment)."""
       import subprocess
       try:
           subprocess.run(["alembic", "upgrade", "head"], check=True, cwd="/app/backend")
       except Exception:
           pass  # Migration may fail if already up to date
   ```

The frontend deploys to Vercel with zero config — Next.js is natively supported. The only config needed is the `NEXT_PUBLIC_API_URL` environment variable.

CODING STYLE:
- Procfile: one process per line, standard Railway format

CONSTRAINTS:
- SQLite file persists on Railway's volume — document that PostgreSQL is better for production
- Concurrency=2 for worker (SQLite can't handle more)
- The startup migration is best-effort (pass on failure)
```

---

**Verification after Phase 7:**
1. `cd backend && pytest` — all tests pass
2. README covers every required topic
3. All pages have loading, error, and empty states
4. NavHeader shows user email and logout works
5. Full E2E flow: signup → add repo → scan → findings → triage → compare
