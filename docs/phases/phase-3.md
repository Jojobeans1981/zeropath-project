# Phase 3: LLM-Powered Scanner Engine

## Objective
Build the core scanning pipeline: chunk Python files for LLM context windows, prompt Claude for security analysis, parse structured findings, compute identity hashes for deduplication, persist results — all running as a Celery background task.

## Current State (After Phase 2)
- **Backend:** FastAPI with auth + repo management. Endpoints: health, auth (signup/login/refresh/me), repos (create/list/detail). Models: User, Repository. Scanner module has `git_ops.py` with `clone_repo()` and `discover_python_files()`. Celery worker connected to Redis with a test task.
- **Frontend:** Login/signup, dashboard (repo list + add form), repo detail page, NavHeader component.
- **Database:** SQLite with `users` and `repositories` tables.
- **Key files:** `backend/app/scanner/git_ops.py`, `backend/app/workers/scan_worker.py` (has test task), `backend/app/deps.py` (has `get_current_user`, `get_db`), `backend/app/config.py` (Settings class)

## Architecture Context

### Data Models

**Scan:**
```
Scan
├── id: UUID (PK)
├── repo_id: UUID (FK → repositories.id, indexed)
├── status: String (enum: "queued", "running", "complete", "failed")
├── commit_sha: String (nullable, set after clone)
├── error_message: String (nullable, set on failure)
├── files_scanned: Integer (default 0)
├── started_at: DateTime (nullable)
├── completed_at: DateTime (nullable)
├── created_at: DateTime (UTC)
└── updated_at: DateTime (UTC, auto-updates)
```

**Finding:**
```
Finding
├── id: UUID (PK)
├── scan_id: UUID (FK → scans.id, indexed)
├── identity_hash: String (indexed, for cross-scan dedup)
├── severity: String (enum: "critical", "high", "medium", "low", "informational")
├── vulnerability_type: String (e.g. "SQL Injection")
├── file_path: String
├── line_number: Integer
├── code_snippet: String (the vulnerable line(s))
├── description: String (one-sentence summary)
├── explanation: String (2-4 sentence detailed explanation)
├── created_at: DateTime (UTC)
└── updated_at: DateTime (UTC, auto-updates)
```

### API Endpoints (this phase)
| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| POST | `/api/scans` | Yes | `{ repo_id: string }` | Scan object (status: "queued") |
| GET | `/api/scans/:id` | Yes | — | Scan detail with status |

Scan response shape:
```json
{
  "id": "uuid",
  "repo_id": "uuid",
  "status": "queued",
  "commit_sha": null,
  "error_message": null,
  "files_scanned": 0,
  "started_at": null,
  "completed_at": null,
  "created_at": "2026-03-16T00:00:00Z"
}
```

### Scanner Pipeline Flow
```
POST /api/scans → create Scan(status=queued) → enqueue Celery task
                                                      │
Celery worker picks up task                           ▼
1. Set status → running, record started_at
2. Clone repo → git_ops.clone_repo(url, temp_dir) → commit_sha
3. Discover files → git_ops.discover_python_files(repo_path)
4. Read file contents, chunk → chunker.chunk_files(files, max_tokens=80000)
5. For each chunk → analyzer.analyze_chunk(chunk) → list[RawFinding]
6. For each finding → dedup.compute_identity_hash() → identity_hash
7. Deduplicate within scan (same hash = same finding, keep first)
8. Persist findings to DB
9. Set status → complete, record files_scanned + completed_at
10. On error → set status=failed, record error_message
11. Always → clean up cloned repo directory in finally block
```

## Coding Standards

### Python Backend
- File naming: lowercase snake_case
- All handlers and DB ops: `async def`
- Logging: `[Scanner]` prefix for scanner module, `[Worker]` prefix for Celery tasks
- Error handling: try-except-finally with cleanup in worker
- Comments: minimal, WHY not WHAT

## Deliverables

1. **`backend/app/models/scan.py`** — Scan SQLAlchemy model
2. **`backend/app/models/finding.py`** — Finding SQLAlchemy model
3. **Alembic migration** — creates `scans` and `findings` tables
4. **`backend/app/schemas/scan.py`** — Pydantic request/response models
5. **`backend/app/schemas/finding.py`** — Pydantic response models for findings
6. **`backend/app/scanner/chunker.py`** — file chunking logic
7. **`backend/app/scanner/prompts.py`** — LLM prompt templates
8. **`backend/app/scanner/analyzer.py`** — Claude API calls + JSON output parsing
9. **`backend/app/scanner/dedup.py`** — identity hash computation
10. **`backend/app/workers/scan_worker.py`** — replace test task with real scan pipeline
11. **`backend/app/services/scan_service.py`** — scan CRUD operations
12. **`backend/app/routers/scans.py`** — POST create + GET status endpoints

## Technical Specification

### backend/app/models/scan.py
- Table name: `scans`
- Columns as specified in data model above
- All UUID fields use `uuid4` default
- `status` default: `"queued"`
- `files_scanned` default: `0`
- Relationship: `repo = relationship("Repository", backref="scans")`
- Relationship: `findings = relationship("Finding", backref="scan", cascade="all, delete-orphan")`

### backend/app/models/finding.py
- Table name: `findings`
- Columns as specified in data model above
- Index on `identity_hash` for dedup queries
- Index on `scan_id` for scan→findings lookups

### backend/app/scanner/chunker.py

```python
@dataclass
class FileContent:
    path: str          # relative path within repo
    content: str       # full file content
    line_count: int

@dataclass
class Chunk:
    files: list[FileContent]
    total_tokens: int  # estimated

SECURITY_PATTERNS = [
    "auth", "login", "api", "route", "view", "model", "admin",
    "settings", "config", "db", "sql", "query", "middleware",
    "password", "token", "session", "permission", "secret",
    "crypto", "hash", "sanitize", "validate", "upload"
]
```

- `estimate_tokens(text: str) -> int`: return `len(text) // 4`
- `prioritize_files(files: list[FileContent]) -> list[FileContent]`: sort files so those with security-relevant names come first. A file is "security-relevant" if any pattern in `SECURITY_PATTERNS` appears in its path (case-insensitive). Security-relevant files first, then alphabetical.
- `chunk_files(files: list[FileContent], max_tokens: int = 80000) -> list[Chunk]`:
  1. Prioritize files
  2. For each file: if single file exceeds `max_tokens`, truncate content to fit and append `"\n# [TRUNCATED — file too large for single analysis chunk]"`
  3. Group files into chunks: add files to current chunk until adding the next file would exceed `max_tokens`, then start a new chunk
  4. Never split a file across chunks
  5. Return list of Chunks

### backend/app/scanner/prompts.py

```python
SYSTEM_PROMPT = """You are a senior application security auditor specializing in Python code review. Your task is to analyze the provided Python source code for security vulnerabilities.

You must identify real, exploitable vulnerabilities. Do not report style issues, performance concerns, or theoretical risks that require unlikely conditions. Focus on issues that a malicious actor could realistically exploit.

Vulnerability classes to look for include but are not limited to:
- SQL Injection (raw queries, string formatting in queries)
- Command Injection (subprocess, os.system, os.popen with user input)
- Path Traversal (file operations with user-controlled paths)
- Server-Side Request Forgery (SSRF) (requests to user-controlled URLs)
- Cross-Site Scripting (XSS) (user input rendered in HTML without escaping)
- Insecure Deserialization (pickle.loads, yaml.load without SafeLoader)
- Hardcoded Secrets/Credentials (API keys, passwords, tokens in source)
- Broken Authentication (weak password requirements, missing auth checks)
- Insecure Direct Object References (IDOR) (accessing resources without ownership check)
- Race Conditions (TOCTOU, unprotected shared state)
- Unsafe Regular Expressions (ReDoS)
- Weak Cryptography (MD5/SHA1 for security, ECB mode, small key sizes)
- Information Disclosure (stack traces, debug modes, verbose errors in production)
- XML External Entity (XXE) (parsing XML without disabling external entities)
- Mass Assignment (accepting arbitrary fields from user input into models)

Report ONLY genuine vulnerabilities. If no vulnerabilities are found, return an empty JSON array [].

Respond with ONLY a JSON array. No markdown, no commentary, no explanation outside the JSON."""

USER_PROMPT_TEMPLATE = """Analyze the following Python source files for security vulnerabilities.

{file_sections}

Respond with a JSON array where each element has this exact structure:
{{
  "severity": "critical" | "high" | "medium" | "low" | "informational",
  "vulnerability_type": "Name of the vulnerability class",
  "file_path": "path/to/file.py",
  "line_number": 42,
  "code_snippet": "the vulnerable line(s) of code",
  "description": "One sentence summary of the vulnerability.",
  "explanation": "2-4 sentences explaining why this is vulnerable, how it could be exploited, and how to fix it."
}}

If no vulnerabilities are found, respond with exactly: []"""
```

- `build_file_sections(chunk: Chunk) -> str`: for each file in the chunk, format as:
  ```
  === File: {file.path} ===
  {numbered lines: "1: line_content", "2: line_content", ...}
  ```

- `build_user_prompt(chunk: Chunk) -> str`: call `build_file_sections()`, interpolate into `USER_PROMPT_TEMPLATE`

### backend/app/scanner/analyzer.py

- `analyze_chunk(chunk: Chunk) -> list[dict]`:
  1. Build prompts via `prompts.build_user_prompt(chunk)` and `prompts.SYSTEM_PROMPT`
  2. Call Anthropic API:
     ```python
     client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
     response = client.messages.create(
         model="claude-sonnet-4-20250514",
         max_tokens=4096,
         system=SYSTEM_PROMPT,
         messages=[{"role": "user", "content": user_prompt}]
     )
     ```
  3. Extract text content from response: `response.content[0].text`
  4. Parse JSON: first try `json.loads(text)`, if that fails try regex `re.search(r'\[[\s\S]*\]', text)` and parse the match
  5. If parsing fails entirely, log warning `[Scanner] Failed to parse LLM output for chunk`, return `[]`
  6. Validate each finding dict: must have keys `severity`, `vulnerability_type`, `file_path`, `line_number`, `code_snippet`, `description`, `explanation`. `severity` must be one of `critical/high/medium/low/informational`. `line_number` must be a positive integer. Discard findings that fail validation with a log warning.
  7. On API error (rate limit, timeout): retry once after 5-second sleep. If retry fails, raise.

### backend/app/scanner/dedup.py

- `compute_identity_hash(vuln_type: str, file_path: str, file_content: str, line_number: int) -> str`:
  1. Split `file_content` into lines
  2. Extract context: lines from `max(0, line_number - 3)` to `min(len(lines), line_number + 2)` (5-line window)
  3. Normalize each context line: `line.strip()`, skip lines that are empty or start with `#` after stripping
  4. Join normalized lines with `\n`, lowercase the result
  5. Compute: `hashlib.sha256(f"{vuln_type}::{file_path}::{normalized_context}".encode()).hexdigest()`

### backend/app/workers/scan_worker.py
- Remove the test task
- Create Celery app: `celery_app = Celery("zeropath", broker=settings.redis_url)`
- Task `run_scan(scan_id: str)`:
  - **Important:** This is a synchronous Celery task. Use synchronous DB sessions (not async). Create a separate `get_sync_session()` in database.py using `create_engine` (not `create_async_engine`) with the sync SQLite URL (`sqlite:///./zeropath.db` instead of `sqlite+aiosqlite:///./zeropath.db`).
  - Pipeline steps 1-11 as described in the pipeline flow above
  - Log each step with `[Worker]` prefix
  - Wrap entire pipeline in try-except-finally:
    - `except`: set scan status to `failed`, set `error_message` to `str(exception)`
    - `finally`: clean up temp directory via `shutil.rmtree(temp_dir, ignore_errors=True)`

### backend/app/services/scan_service.py
- `create_scan(db, repo_id, user_id) -> Scan`:
  1. Verify repo exists and belongs to user → 404/403
  2. Create Scan with `status="queued"`, `repo_id=repo_id`
  3. Commit to DB
  4. Enqueue Celery task: `scan_worker.run_scan.delay(str(scan.id))`
  5. Return scan
- `get_scan(db, scan_id, user_id) -> Scan`:
  1. Get scan by ID, join to repo, verify repo belongs to user
  2. Return scan or raise 404

### backend/app/routers/scans.py
- Router prefix: `/api/scans`
- `POST /`: `create_scan`, return wrapped `ScanResponse`
- `GET /{scan_id}`: `get_scan`, return wrapped `ScanResponse`

### backend/app/schemas/scan.py
- `CreateScanRequest(BaseModel)`: `repo_id: str`
- `ScanResponse(BaseModel)`: `id: str`, `repo_id: str`, `status: str`, `commit_sha: str | None`, `error_message: str | None`, `files_scanned: int`, `started_at: datetime | None`, `completed_at: datetime | None`, `created_at: datetime`

### backend/app/schemas/finding.py
- `FindingResponse(BaseModel)`: `id: str`, `scan_id: str`, `identity_hash: str`, `severity: str`, `vulnerability_type: str`, `file_path: str`, `line_number: int`, `code_snippet: str`, `description: str`, `explanation: str`, `created_at: datetime`

### backend/app/database.py (modify)
- Add sync engine and session factory for Celery worker:
  ```python
  sync_engine = create_engine(settings.database_url.replace("+aiosqlite", ""))
  SyncSessionLocal = sessionmaker(bind=sync_engine)
  ```

### backend/app/main.py (modify)
- Add: `from app.routers import scans`
- Add: `app.include_router(scans.router)`

### backend/app/models/__init__.py (modify)
- Import Scan and Finding models for Alembic autogenerate

## Acceptance Criteria

1. `POST /api/scans` with valid `repo_id` creates scan with status `"queued"` and returns it
2. `POST /api/scans` with non-existent `repo_id` returns 404
3. Celery worker picks up the queued task and processes it
4. During processing, `GET /api/scans/:id` shows status `"running"`
5. After completion, `GET /api/scans/:id` shows status `"complete"` with `files_scanned > 0` and `completed_at` set
6. Findings are persisted with all required fields: severity, vulnerability_type, file_path, line_number, code_snippet, description, explanation
7. Each finding has a non-empty `identity_hash`
8. Running the same scan twice produces findings with identical `identity_hash` values for the same vulnerabilities
9. If git clone fails (e.g. invalid URL), scan status is `"failed"` with error_message set
10. Cloned repo temp directory is cleaned up after scan completes (success or failure)
11. Files exceeding 80K tokens are truncated with `[TRUNCATED]` marker, not dropped
12. LLM output parsing handles both clean JSON and JSON wrapped in markdown code blocks
