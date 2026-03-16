# Phase 11 (Stretch): Auto-Remediation + Multi-Language

## Objective
Generate LLM-powered fix suggestions for findings, and extend scanning to JavaScript/TypeScript codebases.

## Current State (After Phase 10)
- **Backend:** Complete API with auth (RBAC), repos (private), scans (SARIF, WebSocket, webhooks), findings (triage), comparison. Full scanner pipeline.
- **Frontend:** Complete dashboard with real-time updates, admin panel.
- **Scanner:** Currently only discovers and analyzes `.py` files. Prompts are Python-specific.
- **All Phases 0-10 features complete.**

## Architecture Context

### Schema Changes

New model — Remediation:
```
Remediation
├── id: UUID (PK)
├── finding_id: UUID (FK → findings.id, unique)
├── fixed_code: String (the corrected code)
├── explanation: String (why this fix works)
├── confidence: String (enum: "high", "medium", "low")
├── created_at: DateTime (UTC)
└── updated_at: DateTime (UTC)
```

Extend Finding model:
```
Finding (extend)
├── ...existing fields...
└── language: String (default "python", e.g. "python", "javascript", "typescript")
```

### New API Endpoints
| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| POST | `/api/findings/:id/remediation` | Yes | — | RemediationResponse |
| GET | `/api/findings/:id/remediation` | Yes | — | RemediationResponse (cached) |

### Remediation LLM Prompt
Second LLM call per finding, using the finding's context:
- System prompt: "You are a senior developer fixing a security vulnerability..."
- User prompt: includes the vulnerable code snippet, surrounding file context (~20 lines), the vulnerability description, and the explanation
- Output: JSON `{ "fixed_code": "...", "explanation": "...", "confidence": "high|medium|low" }`

### Multi-Language Support
- `discover_source_files(repo_path, languages=["python"])` replaces `discover_python_files()`
- Language config map:
  ```python
  LANGUAGE_CONFIG = {
      "python": {
          "extensions": [".py"],
          "exclude_dirs": ["venv", "env", ".venv", "__pycache__", ".tox", ".eggs", "site-packages"],
          "system_prompt": PYTHON_SYSTEM_PROMPT,
      },
      "javascript": {
          "extensions": [".js", ".jsx", ".ts", ".tsx"],
          "exclude_dirs": ["node_modules", "dist", "build", ".next", "coverage"],
          "system_prompt": JAVASCRIPT_SYSTEM_PROMPT,
      },
  }
  ```
- Scanner auto-detects languages present in repo and scans each

## Coding Standards
- Python: snake_case, async handlers, `[Remediation]` prefix for fix generation logs
- Never call remediation LLM automatically — only on user request (cost control)
- Cache remediation results (don't regenerate for same finding)

## Deliverables

1. **`backend/app/models/remediation.py`** — Remediation SQLAlchemy model
2. **Alembic migration** — create `remediations` table, add `language` to findings
3. **`backend/app/scanner/prompts.py`** (extend) — remediation prompt + JavaScript system prompt
4. **`backend/app/services/remediation_service.py`** — generate + cache fix suggestions
5. **`backend/app/routers/findings.py`** (extend) — POST + GET remediation endpoints
6. **`backend/app/scanner/git_ops.py`** (extend) — multi-language file discovery
7. **`backend/app/workers/scan_worker.py`** (extend) — multi-language scanning
8. **`frontend/app/components/FindingCard.tsx`** (extend) — remediation display with diff view
9. **`frontend/app/components/RemediationView.tsx`** — code diff component

## Technical Specification

### backend/app/scanner/prompts.py (extend)

Add remediation prompt:
```python
REMEDIATION_SYSTEM_PROMPT = """You are a senior software developer fixing a security vulnerability. You must provide a corrected version of the vulnerable code that eliminates the vulnerability while preserving the original functionality.

Your response must be ONLY a JSON object with this exact structure:
{
  "fixed_code": "the corrected code snippet",
  "explanation": "2-3 sentences explaining what was changed and why it fixes the vulnerability",
  "confidence": "high" | "medium" | "low"
}

Confidence levels:
- high: The fix is straightforward and unlikely to break functionality
- medium: The fix requires assumptions about the surrounding code
- low: The fix may need additional context or testing to verify correctness"""

REMEDIATION_USER_TEMPLATE = """Fix the following security vulnerability.

Vulnerability Type: {vulnerability_type}
Severity: {severity}
File: {file_path}, Line: {line_number}

Description: {description}
Explanation: {explanation}

Vulnerable Code:
```
{code_snippet}
```

Surrounding Context:
```
{surrounding_context}
```

Provide the fixed version of the vulnerable code."""
```

Add JavaScript system prompt:
```python
JAVASCRIPT_SYSTEM_PROMPT = """You are a senior application security auditor specializing in JavaScript and TypeScript code review. Your task is to analyze the provided source code for security vulnerabilities.

[Same structure as PYTHON_SYSTEM_PROMPT but with JS-specific vulnerability classes:]
- Prototype Pollution
- DOM-based XSS
- Server-Side Request Forgery (SSRF)
- NoSQL Injection
- Insecure Direct Object References
- Missing CSRF Protection
- Unsafe use of eval(), Function(), or innerHTML
- Hardcoded Secrets/API Keys
- Path Traversal
- Command Injection (child_process with user input)
- Insecure Deserialization
- Open Redirect
- Missing Security Headers
- JWT Misuse (weak secret, algorithm confusion)

[Same JSON output format as Python prompt]"""
```

### backend/app/services/remediation_service.py
- `get_or_generate_remediation(db, finding_id, user_id) -> Remediation`:
  1. Verify finding exists and user owns it
  2. Check if Remediation record already exists for this finding → if yes, return cached
  3. If not: fetch the finding's details + surrounding file context
  4. Call Claude API with remediation prompts
  5. Parse JSON response (same fallback strategy as analyzer)
  6. Create Remediation record, persist, return
- Getting surrounding context: re-clone or cache? For simplicity, store ~20 lines of context in the finding itself (extend Finding model with `surrounding_context` field), populated during scan.

### backend/app/scanner/git_ops.py (extend)
- Rename `discover_python_files` → keep for backwards compat
- Add `discover_source_files(repo_path: Path, languages: list[str] = None) -> dict[str, list[Path]]`:
  - If `languages` is None, auto-detect: check for `.py`, `.js`, `.ts` files in root and common dirs
  - For each detected language, discover files using `LANGUAGE_CONFIG[lang]["extensions"]` and `LANGUAGE_CONFIG[lang]["exclude_dirs"]`
  - Return `{ "python": [paths...], "javascript": [paths...] }`

### backend/app/workers/scan_worker.py (extend)
- Replace `discover_python_files()` with `discover_source_files()`
- For each language detected:
  1. Use language-specific system prompt from `LANGUAGE_CONFIG`
  2. Chunk and analyze files for that language
  3. Tag findings with `language` field
- Scan summary: `files_scanned` is total across all languages

### frontend/app/components/RemediationView.tsx
Named export `RemediationView`. Props: `{ original: string, fixed: string, explanation: string, confidence: string }`.

- Side-by-side or unified diff view:
  - Left/top: original code with red background for changed lines
  - Right/bottom: fixed code with green background for changed lines
  - Below: explanation text
  - Confidence badge: high (green), medium (yellow), low (red)
- Use simple line-by-line comparison (split by `\n`, compare each line)

### frontend/app/components/FindingCard.tsx (extend)
- Add "Generate Fix" button in expanded view (below triage controls)
- On click: `POST /api/findings/:id/remediation`
- State: `remediation` (RemediationData | null), `generatingFix` (boolean)
- While generating: show spinner on button
- When remediation exists: render `<RemediationView>` component
- On subsequent expansions: `GET /api/findings/:id/remediation` (check cache first)
- Show language badge next to severity badge (if not python): `[JS]`, `[TS]`, `[PY]`

## Acceptance Criteria

1. `POST /api/findings/:id/remediation` generates a fix and returns it
2. Second call to same endpoint returns cached result (no LLM call)
3. `GET /api/findings/:id/remediation` returns cached remediation
4. Remediation includes fixed_code, explanation, and confidence
5. "Generate Fix" button in UI triggers remediation and displays result
6. Diff view correctly highlights changed lines (red/green)
7. Scanner discovers `.js`, `.ts`, `.jsx`, `.tsx` files when present
8. JavaScript/TypeScript files are analyzed with JS-specific prompts
9. Findings include correct `language` field
10. Scanning a repo with both Python and JavaScript produces findings for both
11. Language badge shows in FindingCard for non-Python findings
