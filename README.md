# ZeroPath Security Scanner

An LLM-powered security scanner that analyzes Python repositories for vulnerabilities using Claude. Upload a GitHub or GitLab repo URL, and the scanner clones it, chunks the Python files, sends them to Claude for analysis, and presents findings with severity ratings, code snippets, and remediation guidance — all wrapped in a triage workflow that persists across re-scans.

## Quick Start

**Prerequisites:** Python 3.9+, Node.js 20+, Redis (via Docker), an [Anthropic API key](https://console.anthropic.com/)

```bash
# 1. Clone and configure
git clone <repo-url> && cd zeropath-security-scanner
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY and JWT_SECRET

# 2. Start Redis
docker-compose up -d

# 3. Backend
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000 &
celery -A app.workers.scan_worker worker --loglevel=info &

# 4. Frontend
cd ../frontend
npm install
npm run dev
```

Open http://localhost:3000 — sign up, add a repo, run a scan.

## Architecture Overview

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│  Browser  │────▶│  Next.js 14  │────▶│  FastAPI API  │
│  (React)  │◀────│  (Tailwind)  │◀────│  (async)      │
└──────────┘     └──────────────┘     └──────┬───────┘
                                              │
                          ┌───────────────────┼───────────────────┐
                          │                   │                   │
                    ┌─────▼─────┐     ┌──────▼──────┐     ┌─────▼─────┐
                    │  SQLite    │     │   Celery     │     │  Alembic  │
                    │  Database  │     │   Worker     │     │  Migrate  │
                    └───────────┘     └──────┬───────┘     └───────────┘
                                              │
                                    ┌─────────┼─────────┐
                                    │                   │
                              ┌─────▼─────┐     ┌──────▼──────┐
                              │   Redis    │     │  Claude API  │
                              │  (broker)  │     │  (Sonnet)    │
                              └───────────┘     └─────────────┘
```

**Request flow:** Browser → Next.js → FastAPI REST API → SQLite for data, Celery for async scan jobs. The Celery worker clones the repo, chunks Python files, sends each chunk to Claude, validates + deduplicates findings, and persists them to the database.

## Prompt Design

The scanner uses a two-part prompt strategy:

**System prompt** — establishes a "senior application security auditor" persona and enumerates 15+ vulnerability classes (SQLi, XSS, SSRF, command injection, path traversal, insecure deserialization, hardcoded secrets, IDOR, etc.). It explicitly instructs:

- Report only genuine, exploitable vulnerabilities
- No style issues, no theoretical risks
- Respond with ONLY a JSON array — no markdown, no commentary

**User prompt** — presents the code with line numbers and requests a specific JSON schema:

```
=== File: app/routes/users.py ===
1: from flask import request
2: @app.route("/users")
3: def get_users():
4:     query = f"SELECT * FROM users WHERE name = '{request.args['name']}'"
...

Respond with a JSON array where each element has:
{
  "severity": "critical" | "high" | "medium" | "low" | "informational",
  "vulnerability_type": "...",
  "file_path": "...",
  "line_number": 42,
  "code_snippet": "...",
  "description": "One sentence summary.",
  "explanation": "2-4 sentences on why, how to exploit, how to fix."
}
```

**Why single-prompt-per-chunk:** Simpler than multi-turn, more reliable JSON output, and each chunk is self-contained. Multi-turn risks the model losing context of earlier files.

## LLM Output Parsing

The parser is deliberately defensive — LLM output is unpredictable:

1. **Primary:** `json.loads(text.strip())` — works when Claude follows instructions
2. **Fallback:** Regex extraction `\[[\s\S]*\]` — catches JSON wrapped in markdown code fences or explanatory text
3. **Per-finding validation:** Every finding is checked for required keys, valid severity enum, and positive line number
4. **Graceful degradation:** Invalid findings are logged and discarded, not surfaced to users. Unparseable responses return an empty array rather than crashing.

## Token & Context Window Management

- **Estimation:** ~4 characters per token (rough but sufficient for chunking decisions)
- **Chunk size:** 80,000 tokens max per API call — leaves headroom within Claude's context window
- **File integrity:** Files are never split mid-file. A file either fits in the current chunk or starts a new one
- **Priority ordering:** Files with security-relevant names (`auth`, `login`, `config`, `admin`, `password`, etc.) are analyzed first
- **Oversized files:** Truncated with a `[TRUNCATED]` marker rather than skipped entirely

**Why file-level grouping (not function-level):** Function extraction requires AST parsing that would fail on syntax errors. File-level is simpler, more robust, and gives the LLM surrounding context (imports, class structure) that aids vulnerability detection.

## Finding Identity & Stability

Each finding gets a stable identity hash: `SHA-256(vulnerability_type + file_path + normalized_context)` where context is a 5-line window centered on the vulnerability.

**Normalization rules:**
- Strip leading/trailing whitespace from each line
- Remove empty lines and comment-only lines
- Lowercase everything

**Why content-based (not line-number-based):** Line numbers shift when code is edited. A finding at line 42 in one scan might be at line 45 after a refactor. By hashing the surrounding code content, the same vulnerability maintains the same identity even when line numbers change.

**Triage carry-forward:** When a new scan completes, the worker looks for findings in the previous scan with matching identity hashes and copies their triage statuses (open/false_positive/resolved) to the new findings. This means reviewers don't have to re-triage known issues after every scan.

**Known limitation:** If the code around a vulnerability changes significantly (even cosmetically), the identity hash will differ and triage won't carry forward. This is a trade-off — too loose a match would incorrectly link unrelated findings.

## What I Chose Not to Build

- **GitHub/GitLab OAuth:** Used email/password auth instead. OAuth adds complexity (callback URLs, token refresh flows) without meaningfully improving the security scanner's core value. In production, I'd add it.
- **PostgreSQL:** Used SQLite for simplicity. The async SQLAlchemy layer means switching to Postgres requires only changing the connection string.
- **Rate limiting:** Not implemented. In production, I'd add per-user rate limits on scan creation to prevent abuse.
- **WebSocket for scan progress:** Used 5-second polling instead. Simpler to implement and debug. WebSockets would be better UX for long scans.
- **Multi-language support:** Python-only. The architecture (chunker, prompts, analyzer) is language-agnostic — adding new languages means new file discovery patterns and adjusted prompts.
- **RBAC / team features:** Single-user per account. The triage model already has a `user_id` foreign key, so multi-user support is structurally ready.

## What I'd Build Next

1. **Streaming scan progress** — WebSocket or SSE showing which file is being analyzed in real-time
2. **Structured output** — Use Claude's tool_use for guaranteed JSON schema compliance instead of text parsing
3. **Diff-aware scanning** — Only analyze files changed between commits, not the entire repo
4. **GitHub App integration** — Auto-scan on PR creation, post findings as review comments
5. **Finding suppression rules** — Allow users to suppress by pattern (e.g., "ignore all XSS in test files")
6. **PostgreSQL + connection pooling** — For production multi-user workloads
7. **Caching layer** — Don't re-analyze unchanged files across scans

## Known Limitations

- **SQLite:** Single-writer, no concurrent scans. Fine for demo, not for production.
- **No private repo support:** Clone uses public HTTPS. Private repos would need GitHub token injection (the `github_token` parameter exists but is unused).
- **Token estimation is rough:** 4 chars/token is approximate. Some chunks may slightly exceed the context window.
- **No retry on clone failure:** If git clone times out (120s), the scan fails. No automatic retry.
- **Triage carry-forward is best-effort:** If it fails, the scan still completes — triage just won't be copied.
- **No email verification:** Signup accepts any email format without verifying ownership.
- **Celery worker concurrency:** Set to 2 because SQLite can't handle concurrent writes well.

## API Reference

Start the backend and visit http://localhost:8000/docs for the interactive Swagger UI.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/signup` | Create account |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user |
| POST | `/api/repos/` | Add repository |
| GET | `/api/repos/` | List repositories |
| GET | `/api/repos/:id` | Repo detail + scan history |
| POST | `/api/scans/` | Start new scan |
| GET | `/api/scans/:id` | Scan status |
| GET | `/api/scans/:id/findings` | Findings (filterable by severity) |
| GET | `/api/scans/compare` | Compare two scans |
| GET | `/api/findings/:id` | Finding detail |
| PATCH | `/api/findings/:id/triage` | Update triage status |

## Tech Stack

| Component | Technology | Version | Why |
|-----------|-----------|---------|-----|
| Backend framework | FastAPI | 0.115.6 | Async, auto-docs, Pydantic validation |
| Task queue | Celery | 5.4.0 | Battle-tested background job processing |
| Message broker | Redis | 7 (Alpine) | Simple, fast, Celery's recommended broker |
| Database | SQLite + aiosqlite | 0.20.0 | Zero-config, sufficient for single-user demo |
| ORM | SQLAlchemy | 2.0.36 | Async support, Alembic migrations |
| Auth | python-jose + passlib | 3.3.0 / 1.7.4 | JWT tokens + bcrypt hashing |
| LLM | Anthropic Claude Sonnet | 0.52.0 SDK | Best balance of speed, cost, and code analysis quality |
| Frontend | Next.js 14 | 14.2.x | React SSR, file-based routing, TypeScript |
| Styling | Tailwind CSS | 3.x | Utility-first, no CSS files to manage |
| Git operations | GitPython | 3.1.43 | Shallow clone + file discovery |
