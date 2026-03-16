# Phase 11 (Stretch): Auto-Remediation + Multi-Language — Implementation Prompts

## Prompt 11.1 — Remediation Model + Service

```
ROLE: You are implementing LLM-powered fix suggestions for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/finding.py` — Finding model (vulnerability_type, severity, file_path, line_number, code_snippet, description, explanation)
- `backend/app/config.py` — settings.anthropic_api_key
- `backend/app/scanner/prompts.py` — SYSTEM_PROMPT for analysis
- `backend/app/scanner/analyzer.py` — parse_llm_response() for JSON extraction
- `anthropic` package available

TASK:

1. CREATE `backend/app/models/remediation.py`:
   ```python
   import uuid
   from sqlalchemy import Column, String, DateTime, ForeignKey
   from sqlalchemy.dialects.sqlite import CHAR
   from sqlalchemy.orm import relationship
   from app.database import Base
   from app.models.user import utcnow


   class Remediation(Base):
       __tablename__ = "remediations"

       id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       finding_id = Column(CHAR(36), ForeignKey("findings.id"), unique=True, nullable=False)
       fixed_code = Column(String, nullable=False)
       explanation = Column(String, nullable=False)
       confidence = Column(String, nullable=False, default="medium")
       created_at = Column(DateTime, default=utcnow)
       updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

       finding = relationship("Finding", backref="remediation")
   ```

2. MODIFY `backend/app/models/__init__.py` — add Remediation import

3. Run migration: `alembic revision --autogenerate -m "create_remediations_table"` then `alembic upgrade head`

4. ADD to `backend/app/scanner/prompts.py`:
   ```python
   REMEDIATION_SYSTEM_PROMPT = """You are a senior software developer fixing a security vulnerability. Provide a corrected version of the vulnerable code that eliminates the vulnerability while preserving functionality.

   Respond with ONLY a JSON object:
   {
     "fixed_code": "the corrected code snippet",
     "explanation": "2-3 sentences explaining what was changed and why",
     "confidence": "high" | "medium" | "low"
   }

   Confidence: high = straightforward fix, medium = requires assumptions about surrounding code, low = may need additional context."""

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

   Provide the fixed version of the vulnerable code only."""
   ```

5. CREATE `backend/app/services/remediation_service.py`:
   ```python
   import json
   import logging
   import anthropic
   from fastapi import HTTPException
   from sqlalchemy import select
   from sqlalchemy.ext.asyncio import AsyncSession

   from app.config import settings
   from app.models.finding import Finding
   from app.models.remediation import Remediation
   from app.models.scan import Scan
   from app.models.repository import Repository
   from app.scanner.prompts import REMEDIATION_SYSTEM_PROMPT, REMEDIATION_USER_TEMPLATE
   from app.scanner.analyzer import parse_llm_response

   logger = logging.getLogger(__name__)


   async def get_or_generate_remediation(
       db: AsyncSession,
       finding_id: str,
       user_id: str,
   ) -> Remediation:
       # Verify ownership
       result = await db.execute(
           select(Finding).join(Scan).join(Repository).where(Finding.id == finding_id)
       )
       finding = result.scalar_one_or_none()
       if not finding:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Finding not found."}})
       if finding.scan.repo.user_id != user_id:
           raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})

       # Check cache
       existing = await db.execute(
           select(Remediation).where(Remediation.finding_id == finding_id)
       )
       cached = existing.scalar_one_or_none()
       if cached:
           return cached

       # Generate fix via LLM
       logger.info("[Remediation] Generating fix for finding %s", finding_id)
       client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

       user_prompt = REMEDIATION_USER_TEMPLATE.format(
           vulnerability_type=finding.vulnerability_type,
           severity=finding.severity,
           file_path=finding.file_path,
           line_number=finding.line_number,
           description=finding.description,
           explanation=finding.explanation,
           code_snippet=finding.code_snippet,
       )

       response = client.messages.create(
           model="claude-sonnet-4-20250514",
           max_tokens=2048,
           system=REMEDIATION_SYSTEM_PROMPT,
           messages=[{"role": "user", "content": user_prompt}],
       )

       text = response.content[0].text

       # Parse response
       try:
           # Try direct JSON parse
           data = json.loads(text.strip())
       except json.JSONDecodeError:
           # Try extracting JSON object
           import re
           match = re.search(r'\{[\s\S]*\}', text)
           if match:
               data = json.loads(match.group())
           else:
               data = {"fixed_code": text, "explanation": "Auto-generated fix", "confidence": "low"}

       # Validate confidence
       confidence = data.get("confidence", "medium")
       if confidence not in ("high", "medium", "low"):
           confidence = "medium"

       # Persist
       remediation = Remediation(
           finding_id=finding_id,
           fixed_code=data.get("fixed_code", ""),
           explanation=data.get("explanation", ""),
           confidence=confidence,
       )
       db.add(remediation)
       await db.commit()
       await db.refresh(remediation)

       logger.info("[Remediation] Generated fix with confidence: %s", confidence)
       return remediation
   ```

6. ADD to `backend/app/routers/findings.py`:
   ```python
   from app.services import remediation_service

   @router.post("/{finding_id}/remediation")
   async def generate_remediation(
       finding_id: str,
       current_user: User = Depends(get_current_user),
       db: AsyncSession = Depends(get_db),
   ):
       remediation = await remediation_service.get_or_generate_remediation(db, finding_id, current_user.id)
       return {
           "success": True,
           "data": {
               "id": remediation.id,
               "fixed_code": remediation.fixed_code,
               "explanation": remediation.explanation,
               "confidence": remediation.confidence,
               "created_at": remediation.created_at.isoformat(),
           },
       }

   @router.get("/{finding_id}/remediation")
   async def get_remediation(
       finding_id: str,
       current_user: User = Depends(get_current_user),
       db: AsyncSession = Depends(get_db),
   ):
       # Same function — returns cached if exists, generates if not
       remediation = await remediation_service.get_or_generate_remediation(db, finding_id, current_user.id)
       return {
           "success": True,
           "data": {
               "id": remediation.id,
               "fixed_code": remediation.fixed_code,
               "explanation": remediation.explanation,
               "confidence": remediation.confidence,
               "created_at": remediation.created_at.isoformat(),
           },
       }
   ```

CODING STYLE:
- Cache-first: always check DB before calling LLM
- `[Remediation]` log prefix
- Async handler but synchronous Anthropic client call (blocking in async is fine for a take-home)

CONSTRAINTS:
- Remediation is generated on-demand, never automatically (cost control)
- One remediation per finding (unique constraint on finding_id)
- Second call to same finding returns cached result
```

## Prompt 11.2 — Multi-Language Scanning

```
ROLE: You are extending the scanner to support JavaScript and TypeScript for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/scanner/git_ops.py` — discover_python_files()
- `backend/app/scanner/prompts.py` — SYSTEM_PROMPT (Python-specific)
- `backend/app/scanner/chunker.py` — FileContent, chunk_files()
- `backend/app/workers/scan_worker.py` — run_scan() calls discover_python_files()
- `backend/app/models/finding.py` — Finding model

TASK:

1. ADD `language` column to Finding model:
   ```python
   language = Column(String, default="python", nullable=False)
   ```
   Run migration.

2. ADD to `backend/app/scanner/prompts.py`:
   ```python
   JAVASCRIPT_SYSTEM_PROMPT = """You are a senior application security auditor specializing in JavaScript and TypeScript code review. Your task is to analyze the provided source code for security vulnerabilities.

   You must identify real, exploitable vulnerabilities. Do not report style issues, performance concerns, or theoretical risks.

   Vulnerability classes to look for include but are not limited to:
   - Prototype Pollution (modifying Object.prototype via user input)
   - DOM-based XSS (innerHTML, document.write with user input)
   - Server-Side Request Forgery (SSRF)
   - NoSQL Injection (MongoDB query injection)
   - Command Injection (child_process with user input)
   - Path Traversal (fs operations with user-controlled paths)
   - Insecure Deserialization
   - Hardcoded Secrets/API Keys
   - Missing CSRF Protection
   - Unsafe eval(), Function(), or innerHTML usage
   - Open Redirect
   - JWT Misuse (weak secret, algorithm confusion, no expiry)
   - Missing Security Headers
   - Insecure Direct Object References (IDOR)

   Report ONLY genuine vulnerabilities. If none found, return [].
   Respond with ONLY a JSON array. No markdown, no commentary."""
   ```

3. ADD to `backend/app/scanner/git_ops.py`:
   ```python
   LANGUAGE_CONFIG = {
       "python": {
           "extensions": [".py"],
           "skip_dirs": {"venv", "env", ".venv", "__pycache__", ".tox", ".eggs", "site-packages", ".mypy_cache", ".pytest_cache"},
       },
       "javascript": {
           "extensions": [".js", ".jsx", ".ts", ".tsx"],
           "skip_dirs": {"node_modules", "dist", "build", ".next", "coverage", "vendor", "bower_components"},
       },
   }


   def discover_source_files(repo_path: Path) -> dict[str, list[Path]]:
       """Discover source files for all detected languages. Returns {language: [relative_paths]}."""
       result = {}
       for lang, config in LANGUAGE_CONFIG.items():
           files = []
           for ext in config["extensions"]:
               for path in repo_path.rglob(f"*{ext}"):
                   parts = path.relative_to(repo_path).parts
                   if any(part in config["skip_dirs"] or part in SKIP_DIRS for part in parts):
                       continue
                   files.append(path.relative_to(repo_path))
           if files:
               files.sort()
               result[lang] = files
               logger.info("[Scanner] Discovered %d %s files", len(files), lang)
       return result
   ```

4. ADD `LANGUAGE_PROMPTS` map to `backend/app/scanner/prompts.py`:
   ```python
   LANGUAGE_PROMPTS = {
       "python": SYSTEM_PROMPT,
       "javascript": JAVASCRIPT_SYSTEM_PROMPT,
   }
   ```

5. MODIFY `backend/app/workers/scan_worker.py`:
   Replace the single-language flow with multi-language:
   ```python
   # 4. Discover files (multi-language)
   from app.scanner.git_ops import discover_source_files
   from app.scanner.prompts import LANGUAGE_PROMPTS

   files_by_lang = discover_source_files(temp_dir)
   if not files_by_lang:
       # ...set complete with 0 files...
       return

   total_files = 0
   all_findings = []

   for lang, file_paths in files_by_lang.items():
       system_prompt = LANGUAGE_PROMPTS.get(lang, SYSTEM_PROMPT)

       # Read file contents
       file_contents = []
       for rel_path in file_paths:
           full_path = temp_dir / rel_path
           try:
               content = full_path.read_text(encoding="utf-8", errors="replace")
               file_contents.append(FileContent(path=str(rel_path), content=content, line_count=content.count("\n") + 1))
           except Exception as e:
               logger.warning("[Worker] Could not read %s: %s", rel_path, e)

       total_files += len(file_contents)

       # Chunk and analyze
       chunks = chunk_files(file_contents)
       for i, chunk in enumerate(chunks):
           logger.info("[Worker] Analyzing %s chunk %d/%d", lang, i + 1, len(chunks))
           # Pass system_prompt to analyzer
           findings = analyze_chunk(chunk, system_prompt=system_prompt)
           # Tag with language
           for f in findings:
               f["language"] = lang
           all_findings.extend(findings)
   ```

6. MODIFY `backend/app/scanner/analyzer.py`:
   - Add `system_prompt` parameter to `analyze_chunk()`:
     ```python
     def analyze_chunk(chunk: Chunk, max_retries: int = 1, system_prompt: str | None = None) -> list[dict]:
         if system_prompt is None:
             system_prompt = SYSTEM_PROMPT
     ```
   - Use the passed `system_prompt` in the API call

7. MODIFY worker to persist `language` on findings:
   ```python
   finding = Finding(
       ...existing fields...,
       language=raw.get("language", "python"),
   )
   ```

CODING STYLE:
- Language detection is automatic (based on file extensions found)
- Each language gets its own system prompt
- Findings tagged with source language

CONSTRAINTS:
- Default to Python system prompt if language not in LANGUAGE_PROMPTS
- Do NOT change the chunker — it works the same regardless of language
- Multi-language scanning runs all languages in sequence (not parallel)
```

## Prompt 11.3 — Frontend Remediation + Language Badge

```
ROLE: You are adding remediation UI and language badges to the ZeroPath frontend.

CONTEXT:
- `frontend/app/components/FindingCard.tsx` — expandable card with triage controls
- Backend: POST/GET /api/findings/:id/remediation → {fixed_code, explanation, confidence}
- Findings now include `language` field ("python", "javascript")

TASK:

1. CREATE `frontend/app/components/RemediationView.tsx`:
   ```tsx
   "use client";

   interface RemediationViewProps {
     original: string;
     fixed: string;
     explanation: string;
     confidence: string;
   }

   const CONFIDENCE_COLORS: Record<string, string> = {
     high: "bg-green-100 text-green-800",
     medium: "bg-yellow-100 text-yellow-800",
     low: "bg-red-100 text-red-800",
   };

   export function RemediationView({ original, fixed, explanation, confidence }: RemediationViewProps) {
     return (
       <div className="space-y-3">
         <div className="flex items-center gap-2">
           <span className="text-sm font-medium text-gray-700">Suggested Fix</span>
           <span className={`px-2 py-0.5 rounded text-xs font-medium ${CONFIDENCE_COLORS[confidence] || CONFIDENCE_COLORS.medium}`}>
             {confidence} confidence
           </span>
         </div>

         <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
           <div>
             <p className="text-xs text-red-600 font-medium mb-1">Original (vulnerable)</p>
             <pre className="bg-red-950 text-red-200 text-xs p-3 rounded-lg overflow-x-auto">
               <code>{original}</code>
             </pre>
           </div>
           <div>
             <p className="text-xs text-green-600 font-medium mb-1">Fixed</p>
             <pre className="bg-green-950 text-green-200 text-xs p-3 rounded-lg overflow-x-auto">
               <code>{fixed}</code>
             </pre>
           </div>
         </div>

         <p className="text-sm text-gray-600">{explanation}</p>
       </div>
     );
   }
   ```

2. MODIFY `frontend/app/components/FindingCard.tsx`:

   Add to Finding interface:
   ```typescript
   language?: string;
   ```

   Add state:
   ```typescript
   const [remediation, setRemediation] = useState<{fixed_code: string; explanation: string; confidence: string} | null>(null);
   const [generatingFix, setGeneratingFix] = useState(false);
   ```

   Add language badge in collapsed header (after severity badge):
   ```tsx
   {finding.language && finding.language !== "python" && (
     <span className="px-1.5 py-0.5 rounded text-xs font-mono bg-purple-100 text-purple-800">
       {finding.language === "javascript" ? "JS/TS" : finding.language.toUpperCase()}
     </span>
   )}
   ```

   Add "Generate Fix" button in expanded section (after triage controls):
   ```tsx
   <div className="border-t border-gray-100 pt-3 mt-3">
     {!remediation ? (
       <button
         onClick={handleGenerateFix}
         disabled={generatingFix}
         className="px-4 py-1.5 bg-purple-600 text-white text-sm rounded-lg hover:bg-purple-700 disabled:opacity-50"
       >
         {generatingFix ? "Generating fix..." : "Generate Fix Suggestion"}
       </button>
     ) : (
       <RemediationView
         original={finding.code_snippet}
         fixed={remediation.fixed_code}
         explanation={remediation.explanation}
         confidence={remediation.confidence}
       />
     )}
   </div>
   ```

   handleGenerateFix:
   ```typescript
   const handleGenerateFix = async () => {
     setGeneratingFix(true);
     const res = await apiFetch<{fixed_code: string; explanation: string; confidence: string}>(
       `/api/findings/${finding.id}/remediation`,
       { method: "POST" }
     );
     if (res.success && res.data) {
       setRemediation(res.data);
     }
     setGeneratingFix(false);
   };
   ```

CODING STYLE:
- RemediationView is a pure display component
- Side-by-side diff view on desktop, stacked on mobile
- Purple color scheme for remediation (distinct from triage blue)

CONSTRAINTS:
- "Generate Fix" calls POST (generates), subsequent loads use cached
- Language badge only shown for non-Python findings (Python is the default)
- RemediationView shows original vs fixed code, not a unified diff
```

---

**Verification after Phase 11:**
1. POST /api/findings/:id/remediation generates and returns fix
2. Second call returns cached result (no LLM call)
3. "Generate Fix" button works in FindingCard
4. RemediationView shows side-by-side original vs fixed code
5. JS/TS files are discovered and analyzed with JS-specific prompts
6. Findings include correct language field
7. Language badge appears for JavaScript findings
