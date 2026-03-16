# Phase 3: LLM-Powered Scanner Engine — Implementation Prompts

## Prompt 3.1 — Scan + Finding Models + Migration

```
ROLE: You are implementing the Scan and Finding database models for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/database.py` — exports Base, engines, sessions, get_db()
- `backend/app/models/user.py` — User model, exports utcnow() helper
- `backend/app/models/repository.py` — Repository model (id, user_id, url, name)
- `backend/app/models/__init__.py` — imports User, Repository

TASK:
Create the Scan and Finding models, update model imports, and generate migration.

CREATE:

1. `backend/app/models/scan.py`:
   ```python
   import uuid
   from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
   from sqlalchemy.dialects.sqlite import CHAR
   from sqlalchemy.orm import relationship
   from app.database import Base
   from app.models.user import utcnow


   class Scan(Base):
       __tablename__ = "scans"

       id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       repo_id = Column(CHAR(36), ForeignKey("repositories.id"), index=True, nullable=False)
       status = Column(String, default="queued", nullable=False)
       commit_sha = Column(String, nullable=True)
       error_message = Column(String, nullable=True)
       files_scanned = Column(Integer, default=0)
       started_at = Column(DateTime, nullable=True)
       completed_at = Column(DateTime, nullable=True)
       created_at = Column(DateTime, default=utcnow)
       updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

       repo = relationship("Repository", backref="scans")
       findings = relationship("Finding", backref="scan", cascade="all, delete-orphan")
   ```

2. `backend/app/models/finding.py`:
   ```python
   import uuid
   from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Index
   from sqlalchemy.dialects.sqlite import CHAR
   from app.database import Base
   from app.models.user import utcnow


   class Finding(Base):
       __tablename__ = "findings"

       id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       scan_id = Column(CHAR(36), ForeignKey("scans.id"), index=True, nullable=False)
       identity_hash = Column(String, index=True, nullable=False)
       severity = Column(String, nullable=False)
       vulnerability_type = Column(String, nullable=False)
       file_path = Column(String, nullable=False)
       line_number = Column(Integer, nullable=False)
       code_snippet = Column(String, nullable=False)
       description = Column(String, nullable=False)
       explanation = Column(String, nullable=False)
       created_at = Column(DateTime, default=utcnow)
       updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
   ```

3. MODIFY `backend/app/models/__init__.py`:
   ```python
   from app.models.user import User
   from app.models.repository import Repository
   from app.models.scan import Scan
   from app.models.finding import Finding

   __all__ = ["User", "Repository", "Scan", "Finding"]
   ```

4. Run: `alembic revision --autogenerate -m "create_scans_and_findings_tables"` then `alembic upgrade head`

CONSTRAINTS:
- Status values: "queued", "running", "complete", "failed" — stored as plain strings, no enum column type
- Severity values: "critical", "high", "medium", "low", "informational" — stored as plain strings
- Do NOT create routes or services yet
```

## Prompt 3.2 — Scan Schemas + Service + Router

```
ROLE: You are implementing the scan creation API for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- Models: User, Repository, Scan, Finding — all in DB
- `backend/app/deps.py` — get_current_user(), get_db()
- `backend/app/services/repo_service.py` — get_repo(db, user_id, repo_id) verifies ownership
- `backend/app/workers/scan_worker.py` — has celery_app, currently only has test_task
- `backend/app/main.py` — includes auth and repos routers

TASK:
Create scan schemas, scan service, scan router. The scan creation endpoint enqueues a Celery task.

CREATE:

1. `backend/app/schemas/scan.py`:
   ```python
   from datetime import datetime
   from pydantic import BaseModel


   class CreateScanRequest(BaseModel):
       repo_id: str


   class ScanResponse(BaseModel):
       id: str
       repo_id: str
       status: str
       commit_sha: str | None = None
       error_message: str | None = None
       files_scanned: int = 0
       started_at: datetime | None = None
       completed_at: datetime | None = None
       created_at: datetime
   ```

2. `backend/app/schemas/finding.py`:
   ```python
   from datetime import datetime
   from pydantic import BaseModel


   class FindingResponse(BaseModel):
       id: str
       scan_id: str
       identity_hash: str
       severity: str
       vulnerability_type: str
       file_path: str
       line_number: int
       code_snippet: str
       description: str
       explanation: str
       created_at: datetime
   ```

3. `backend/app/services/scan_service.py`:
   ```python
   from fastapi import HTTPException
   from sqlalchemy import select
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.models.scan import Scan
   from app.models.repository import Repository


   async def create_scan(db: AsyncSession, repo_id: str, user_id: str) -> Scan:
       # Verify repo exists and belongs to user
       result = await db.execute(select(Repository).where(Repository.id == repo_id))
       repo = result.scalar_one_or_none()
       if not repo:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Repository not found."}})
       if repo.user_id != user_id:
           raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

       scan = Scan(repo_id=repo_id, status="queued")
       db.add(scan)
       await db.commit()
       await db.refresh(scan)

       # Enqueue Celery task
       from app.workers.scan_worker import run_scan
       run_scan.delay(scan.id)

       return scan


   async def get_scan(db: AsyncSession, scan_id: str, user_id: str) -> Scan:
       result = await db.execute(
           select(Scan).join(Repository).where(Scan.id == scan_id)
       )
       scan = result.scalar_one_or_none()
       if not scan:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Scan not found."}})
       if scan.repo.user_id != user_id:
           raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})
       return scan
   ```

4. `backend/app/routers/scans.py`:
   - Router prefix `/api/scans`, tags `["scans"]`
   - All endpoints require `get_current_user` and `get_db`
   - `POST /`: call create_scan, return `{"success": true, "data": ScanResponse}`
   - `GET /{scan_id}`: call get_scan, return `{"success": true, "data": ScanResponse}`

5. MODIFY `backend/app/main.py` — add:
   ```python
   from app.routers import scans
   app.include_router(scans.router)
   ```

CODING STYLE:
- Async handlers, select() queries
- Response envelope on every endpoint
- Import Celery task lazily to avoid circular imports

CONSTRAINTS:
- The Celery task `run_scan` doesn't exist yet — it will be created in the next prompts
- Import it lazily inside create_scan to avoid import errors during startup
```

## Prompt 3.3 — Scanner: Chunker + Prompts + Dedup

```
ROLE: You are implementing the core scanner components for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/scanner/__init__.py` — empty
- `backend/app/scanner/git_ops.py` — clone_repo() and discover_python_files()
- `backend/app/config.py` — settings.anthropic_api_key

TASK:
Create the file chunker, LLM prompt templates, and identity hash deduplication module.

CREATE:

1. `backend/app/scanner/chunker.py`:
   ```python
   import logging
   from dataclasses import dataclass, field

   logger = logging.getLogger(__name__)

   SECURITY_PATTERNS = [
       "auth", "login", "api", "route", "view", "model", "admin",
       "settings", "config", "db", "sql", "query", "middleware",
       "password", "token", "session", "permission", "secret",
       "crypto", "hash", "sanitize", "validate", "upload",
   ]


   @dataclass
   class FileContent:
       path: str
       content: str
       line_count: int


   @dataclass
   class Chunk:
       files: list[FileContent] = field(default_factory=list)
       total_tokens: int = 0


   def estimate_tokens(text: str) -> int:
       """Rough estimate: ~4 characters per token."""
       return len(text) // 4


   def is_security_relevant(path: str) -> bool:
       path_lower = path.lower()
       return any(pattern in path_lower for pattern in SECURITY_PATTERNS)


   def prioritize_files(files: list[FileContent]) -> list[FileContent]:
       """Sort files: security-relevant first, then alphabetical."""
       security = [f for f in files if is_security_relevant(f.path)]
       other = [f for f in files if not is_security_relevant(f.path)]
       security.sort(key=lambda f: f.path)
       other.sort(key=lambda f: f.path)
       return security + other


   def chunk_files(files: list[FileContent], max_tokens: int = 80000) -> list[Chunk]:
       """Group files into chunks that fit within max_tokens."""
       prioritized = prioritize_files(files)
       chunks: list[Chunk] = []
       current = Chunk()

       for file in prioritized:
           file_tokens = estimate_tokens(file.content)

           # If single file exceeds max, truncate it
           if file_tokens > max_tokens:
               char_limit = max_tokens * 4
               truncated = FileContent(
                   path=file.path,
                   content=file.content[:char_limit] + "\n# [TRUNCATED — file too large for single analysis chunk]",
                   line_count=file.line_count,
               )
               if current.files:
                   chunks.append(current)
                   current = Chunk()
               chunks.append(Chunk(files=[truncated], total_tokens=max_tokens))
               continue

           # If adding this file would exceed limit, start new chunk
           if current.total_tokens + file_tokens > max_tokens and current.files:
               chunks.append(current)
               current = Chunk()

           current.files.append(file)
           current.total_tokens += file_tokens

       if current.files:
           chunks.append(current)

       logger.info("[Scanner] Created %d chunks from %d files", len(chunks), len(files))
       return chunks
   ```

2. `backend/app/scanner/prompts.py`:
   ```python
   from app.scanner.chunker import Chunk

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


   def build_file_sections(chunk: Chunk) -> str:
       sections = []
       for file in chunk.files:
           lines = file.content.split("\n")
           numbered = "\n".join(f"{i+1}: {line}" for i, line in enumerate(lines))
           sections.append(f"=== File: {file.path} ===\n{numbered}")
       return "\n\n".join(sections)


   def build_user_prompt(chunk: Chunk) -> str:
       file_sections = build_file_sections(chunk)
       return USER_PROMPT_TEMPLATE.format(file_sections=file_sections)
   ```

3. `backend/app/scanner/dedup.py`:
   ```python
   import hashlib


   def compute_identity_hash(
       vuln_type: str,
       file_path: str,
       file_content: str,
       line_number: int,
   ) -> str:
       """Compute a stable identity hash for a finding based on content context."""
       lines = file_content.split("\n")
       start = max(0, line_number - 4)  # 3 lines before (0-indexed: line_number - 1 - 3)
       end = min(len(lines), line_number + 1)  # 1 line after (0-indexed: line_number - 1 + 2)
       context_lines = lines[start:end]

       # Normalize: strip whitespace, remove comment-only and empty lines
       normalized = []
       for line in context_lines:
           stripped = line.strip()
           if stripped and not stripped.startswith("#"):
               normalized.append(stripped.lower())

       context = "\n".join(normalized)
       raw = f"{vuln_type}::{file_path}::{context}"
       return hashlib.sha256(raw.encode()).hexdigest()
   ```

CODING STYLE:
- Dataclasses for data structures (not Pydantic — these aren't API schemas)
- Logging with `[Scanner]` prefix
- Type hints on all functions
- No unnecessary abstractions

CONSTRAINTS:
- Do NOT create the analyzer (Claude API calls) — that's the next prompt
- The prompts are Python-specific for now (multi-language is Phase 11)
- Dedup window is 5 lines centered on the vulnerability line
```

## Prompt 3.4 — Scanner: Analyzer (Claude API)

```
ROLE: You are implementing the LLM analyzer that calls the Anthropic Claude API for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/scanner/prompts.py` — SYSTEM_PROMPT, build_user_prompt(chunk) returns formatted user prompt string
- `backend/app/scanner/chunker.py` — Chunk dataclass with files and total_tokens
- `backend/app/config.py` — settings.anthropic_api_key
- `anthropic` package in requirements.txt (version 0.52.0)

TASK:
Create the analyzer module that sends chunks to Claude and parses the JSON response.

CREATE:

1. `backend/app/scanner/analyzer.py`:
   ```python
   import json
   import logging
   import re
   import time

   import anthropic

   from app.config import settings
   from app.scanner.chunker import Chunk
   from app.scanner.prompts import SYSTEM_PROMPT, build_user_prompt

   logger = logging.getLogger(__name__)

   VALID_SEVERITIES = {"critical", "high", "medium", "low", "informational"}
   REQUIRED_KEYS = {"severity", "vulnerability_type", "file_path", "line_number", "code_snippet", "description", "explanation"}


   def parse_llm_response(text: str) -> list[dict]:
       """Parse JSON array from LLM response, handling markdown wrapping."""
       # Try direct parse first
       try:
           result = json.loads(text.strip())
           if isinstance(result, list):
               return result
       except json.JSONDecodeError:
           pass

       # Fallback: extract JSON array from markdown or surrounding text
       match = re.search(r'\[[\s\S]*\]', text)
       if match:
           try:
               result = json.loads(match.group())
               if isinstance(result, list):
                   return result
           except json.JSONDecodeError:
               pass

       logger.warning("[Scanner] Failed to parse LLM output: %.100s...", text)
       return []


   def validate_finding(finding: dict) -> bool:
       """Validate a finding dict has all required fields with correct types."""
       if not isinstance(finding, dict):
           return False
       if not REQUIRED_KEYS.issubset(finding.keys()):
           logger.warning("[Scanner] Finding missing keys: %s", REQUIRED_KEYS - finding.keys())
           return False
       if finding.get("severity", "").lower() not in VALID_SEVERITIES:
           logger.warning("[Scanner] Invalid severity: %s", finding.get("severity"))
           return False
       if not isinstance(finding.get("line_number"), int) or finding["line_number"] < 1:
           logger.warning("[Scanner] Invalid line_number: %s", finding.get("line_number"))
           return False
       return True


   def analyze_chunk(chunk: Chunk, max_retries: int = 1) -> list[dict]:
       """Send a chunk to Claude for security analysis. Returns validated findings."""
       client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
       user_prompt = build_user_prompt(chunk)

       file_names = [f.path for f in chunk.files]
       logger.info("[Scanner] Analyzing chunk with %d files: %s", len(file_names), file_names)

       for attempt in range(max_retries + 1):
           try:
               response = client.messages.create(
                   model="claude-sonnet-4-20250514",
                   max_tokens=4096,
                   system=SYSTEM_PROMPT,
                   messages=[{"role": "user", "content": user_prompt}],
               )

               text = response.content[0].text
               logger.info("[Scanner] Received response (%d chars)", len(text))

               raw_findings = parse_llm_response(text)
               valid = []
               for f in raw_findings:
                   if validate_finding(f):
                       f["severity"] = f["severity"].lower()
                       valid.append(f)
                   else:
                       logger.warning("[Scanner] Discarding invalid finding: %.100s", str(f))

               logger.info("[Scanner] Found %d valid findings in chunk", len(valid))
               return valid

           except anthropic.RateLimitError:
               if attempt < max_retries:
                   logger.warning("[Scanner] Rate limited, retrying in 5s (attempt %d)", attempt + 1)
                   time.sleep(5)
               else:
                   raise
           except anthropic.APIError as e:
               if attempt < max_retries:
                   logger.warning("[Scanner] API error: %s, retrying in 5s", str(e))
                   time.sleep(5)
               else:
                   raise

       return []  # Should not reach here
   ```

CODING STYLE:
- Synchronous code (runs in Celery worker, not async)
- Logging with `[Scanner]` prefix at every key step
- Defensive parsing: never crash on bad LLM output
- Retry once on rate limit or API error

CONSTRAINTS:
- Model is hardcoded to "claude-sonnet-4-20250514"
- max_tokens=4096 for the response (findings are JSON, not long text)
- Do NOT use tool_use / structured output — direct JSON in text is simpler and sufficient
```

## Prompt 3.5 — Celery Worker: Full Scan Pipeline

```
ROLE: You are implementing the full scan pipeline as a Celery background task for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/workers/scan_worker.py` — has celery_app and test_task (to be replaced)
- `backend/app/scanner/git_ops.py` — clone_repo(url, dest, github_token=None) → SHA, discover_python_files(repo_path) → list[Path]
- `backend/app/scanner/chunker.py` — FileContent, Chunk, chunk_files(files, max_tokens=80000)
- `backend/app/scanner/analyzer.py` — analyze_chunk(chunk) → list[dict] with validated findings
- `backend/app/scanner/dedup.py` — compute_identity_hash(vuln_type, file_path, file_content, line_number) → str
- `backend/app/database.py` — SyncSessionLocal (synchronous session factory), sync_engine
- `backend/app/models/scan.py` — Scan model (id, repo_id, status, commit_sha, error_message, files_scanned, started_at, completed_at)
- `backend/app/models/finding.py` — Finding model (id, scan_id, identity_hash, severity, vulnerability_type, file_path, line_number, code_snippet, description, explanation)
- `backend/app/models/repository.py` — Repository model (id, user_id, url, name)
- `backend/app/config.py` — settings.scan_workdir, settings.redis_url

TASK:
Replace the test task with the full scan pipeline. This is a synchronous Celery task using synchronous DB sessions.

REPLACE `backend/app/workers/scan_worker.py` with:

```python
import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from celery import Celery

from app.config import settings
from app.database import SyncSessionLocal
from app.models.finding import Finding
from app.models.repository import Repository
from app.models.scan import Scan
from app.scanner.analyzer import analyze_chunk
from app.scanner.chunker import FileContent, chunk_files
from app.scanner.dedup import compute_identity_hash
from app.scanner.git_ops import clone_repo, discover_python_files

logger = logging.getLogger(__name__)

celery_app = Celery("zeropath", broker=settings.redis_url)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"


@celery_app.task(name="run_scan")
def run_scan(scan_id: str) -> None:
    """Full scan pipeline: clone → discover → chunk → analyze → dedup → persist."""
    db = SyncSessionLocal()
    temp_dir = Path(settings.scan_workdir) / str(uuid.uuid4())

    try:
        # 1. Get scan and repo
        scan = db.query(Scan).filter(Scan.id == scan_id).first()
        if not scan:
            logger.error("[Worker] Scan %s not found", scan_id)
            return
        repo = db.query(Repository).filter(Repository.id == scan.repo_id).first()
        if not repo:
            logger.error("[Worker] Repository %s not found", scan.repo_id)
            return

        # 2. Set status to running
        scan.status = "running"
        scan.started_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[Worker] Starting scan %s for repo %s", scan_id, repo.name)

        # 3. Clone repo
        temp_dir.mkdir(parents=True, exist_ok=True)
        commit_sha = clone_repo(repo.url, temp_dir)
        scan.commit_sha = commit_sha
        db.commit()

        # 4. Discover Python files
        py_files = discover_python_files(temp_dir)
        if not py_files:
            logger.info("[Worker] No Python files found in %s", repo.name)
            scan.status = "complete"
            scan.files_scanned = 0
            scan.completed_at = datetime.now(timezone.utc)
            db.commit()
            return

        # 5. Read file contents
        file_contents = []
        for rel_path in py_files:
            full_path = temp_dir / rel_path
            try:
                content = full_path.read_text(encoding="utf-8", errors="replace")
                file_contents.append(FileContent(
                    path=str(rel_path),
                    content=content,
                    line_count=content.count("\n") + 1,
                ))
            except Exception as e:
                logger.warning("[Worker] Could not read %s: %s", rel_path, e)

        # 6. Chunk files
        chunks = chunk_files(file_contents)
        logger.info("[Worker] Processing %d chunks for %d files", len(chunks), len(file_contents))

        # 7. Analyze each chunk
        all_findings: list[dict] = []
        for i, chunk in enumerate(chunks):
            logger.info("[Worker] Analyzing chunk %d/%d", i + 1, len(chunks))
            findings = analyze_chunk(chunk)
            all_findings.extend(findings)

        # 8. Deduplicate and persist findings
        seen_hashes: set[str] = set()
        persisted_count = 0

        # Build file content lookup for dedup context
        content_map = {fc.path: fc.content for fc in file_contents}

        for raw in all_findings:
            file_content = content_map.get(raw["file_path"], "")
            identity_hash = compute_identity_hash(
                raw["vulnerability_type"],
                raw["file_path"],
                file_content,
                raw["line_number"],
            )

            if identity_hash in seen_hashes:
                logger.info("[Worker] Dedup: skipping duplicate finding %s in %s", raw["vulnerability_type"], raw["file_path"])
                continue
            seen_hashes.add(identity_hash)

            finding = Finding(
                scan_id=scan_id,
                identity_hash=identity_hash,
                severity=raw["severity"],
                vulnerability_type=raw["vulnerability_type"],
                file_path=raw["file_path"],
                line_number=raw["line_number"],
                code_snippet=raw["code_snippet"],
                description=raw["description"],
                explanation=raw["explanation"],
            )
            db.add(finding)
            persisted_count += 1

        # 9. Mark complete
        scan.status = "complete"
        scan.files_scanned = len(file_contents)
        scan.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("[Worker] Scan %s complete: %d files, %d findings", scan_id, len(file_contents), persisted_count)

    except Exception as e:
        logger.exception("[Worker] Scan %s failed: %s", scan_id, str(e))
        try:
            scan = db.query(Scan).filter(Scan.id == scan_id).first()
            if scan:
                scan.status = "failed"
                scan.error_message = str(e)[:500]
                scan.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            logger.exception("[Worker] Failed to update scan status")
    finally:
        db.close()
        if temp_dir.exists():
            shutil.rmtree(str(temp_dir), ignore_errors=True)
            logger.info("[Worker] Cleaned up temp directory %s", temp_dir)
```

CODING STYLE:
- Synchronous code (Celery worker, not async)
- `[Worker]` prefix on all log messages
- try-except-finally with cleanup
- Defensive: handle missing scan, missing repo, unreadable files

CONSTRAINTS:
- Do NOT use async session — Celery tasks are synchronous
- Use db.query() (not select()) since this is synchronous SQLAlchemy
- Temp dir is always cleaned up in finally block
- Error messages truncated to 500 chars to avoid DB issues
- The test_task is removed — this is a full replacement
```

---

**Verification after Phase 3:**
1. `POST /api/scans` with valid repo_id → creates scan with status "queued"
2. Celery worker picks up and processes the scan
3. `GET /api/scans/:id` shows status progression: queued → running → complete
4. Findings are persisted with identity_hash, severity, file_path, line_number, etc.
5. Duplicate findings within a scan are deduplicated
6. Failed scans show error_message
7. Temp directories are cleaned up
