# Phase 2: Repository Management & Git Operations — Implementation Prompts

## Prompt 2.1 — Repository Model + Migration

```
ROLE: You are implementing the Repository model for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/database.py` — exports `Base`, async/sync engines, `get_db()`
- `backend/app/models/user.py` — User model with id (CHAR(36) UUID string PK), email, password_hash, created_at, updated_at. Has `utcnow()` helper function.
- `backend/app/models/__init__.py` — imports User
- Alembic configured and working. `users` table exists.

TASK:
Create the Repository model and generate a migration.

CREATE:

1. `backend/app/models/repository.py`:
   ```python
   import uuid
   from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint
   from sqlalchemy.dialects.sqlite import CHAR
   from sqlalchemy.orm import relationship
   from app.database import Base
   from app.models.user import utcnow


   class Repository(Base):
       __tablename__ = "repositories"
       __table_args__ = (
           UniqueConstraint("user_id", "url", name="uq_user_repo"),
       )

       id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       user_id = Column(CHAR(36), ForeignKey("users.id"), index=True, nullable=False)
       url = Column(String, nullable=False)
       name = Column(String, nullable=False)
       created_at = Column(DateTime, default=utcnow)
       updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

       user = relationship("User", backref="repositories")
   ```

2. MODIFY `backend/app/models/__init__.py`:
   ```python
   from app.models.user import User
   from app.models.repository import Repository

   __all__ = ["User", "Repository"]
   ```

3. Run: `alembic revision --autogenerate -m "create_repositories_table"` then `alembic upgrade head`

CONSTRAINTS:
- Do NOT create routes or schemas yet
- The unique constraint prevents the same user from adding the same URL twice
```

## Prompt 2.2 — Repo Schemas, Service, and Router

```
ROLE: You are implementing repository management API endpoints for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/repository.py` — Repository model with id, user_id, url, name, created_at, updated_at. UniqueConstraint on (user_id, url).
- `backend/app/models/user.py` — User model
- `backend/app/deps.py` — `get_db()` and `get_current_user()` dependencies
- `backend/app/main.py` — FastAPI app with auth router included

API response envelope: `{"success": true, "data": ...}` or `{"success": false, "error": {"code": "...", "message": "..."}}`

TASK:
Create schemas, service, and router for repository CRUD.

CREATE:

1. `backend/app/schemas/repo.py`:
   ```python
   from datetime import datetime
   from pydantic import BaseModel, field_validator


   class CreateRepoRequest(BaseModel):
       url: str

       @field_validator("url")
       @classmethod
       def validate_url(cls, v: str) -> str:
           v = v.rstrip("/").rstrip(".git")
           if not (v.startswith("https://github.com/") or v.startswith("https://gitlab.com/")):
               raise ValueError("URL must start with https://github.com/ or https://gitlab.com/")
           parts = v.split("/")
           if len(parts) < 5:
               raise ValueError("URL must include owner and repository name")
           return v


   class RepoResponse(BaseModel):
       id: str
       url: str
       name: str
       scan_count: int = 0
       created_at: datetime
       updated_at: datetime
   ```

2. `backend/app/services/repo_service.py`:
   ```python
   from fastapi import HTTPException
   from sqlalchemy import select, func
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.models.repository import Repository


   def extract_repo_name(url: str) -> str:
       """Extract 'owner/repo' from a GitHub/GitLab URL."""
       parts = url.rstrip("/").split("/")
       return f"{parts[-2]}/{parts[-1]}"


   async def create_or_get_repo(db: AsyncSession, user_id: str, url: str) -> Repository:
       url = url.rstrip("/").rstrip(".git")
       result = await db.execute(
           select(Repository).where(Repository.user_id == user_id, Repository.url == url)
       )
       existing = result.scalar_one_or_none()
       if existing:
           return existing

       repo = Repository(
           user_id=user_id,
           url=url,
           name=extract_repo_name(url),
       )
       db.add(repo)
       await db.commit()
       await db.refresh(repo)
       return repo


   async def list_repos(db: AsyncSession, user_id: str) -> list[dict]:
       # Import here to avoid circular import (Scan model may not exist yet)
       from app.models import scan as scan_module
       try:
           Scan = scan_module.Scan
           stmt = (
               select(Repository, func.count(Scan.id).label("scan_count"))
               .outerjoin(Scan, Scan.repo_id == Repository.id)
               .where(Repository.user_id == user_id)
               .group_by(Repository.id)
               .order_by(Repository.created_at.desc())
           )
           rows = await db.execute(stmt)
           return [{"repo": repo, "scan_count": count} for repo, count in rows.all()]
       except Exception:
           # Scan model doesn't exist yet (Phase 2 runs before Phase 3)
           result = await db.execute(
               select(Repository).where(Repository.user_id == user_id).order_by(Repository.created_at.desc())
           )
           return [{"repo": repo, "scan_count": 0} for repo in result.scalars().all()]


   async def get_repo(db: AsyncSession, user_id: str, repo_id: str) -> Repository:
       result = await db.execute(select(Repository).where(Repository.id == repo_id))
       repo = result.scalar_one_or_none()
       if not repo:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "Repository not found."}})
       if repo.user_id != user_id:
           raise HTTPException(status_code=403, detail={"error": {"code": "FORBIDDEN", "message": "Access denied."}})
       return repo
   ```

3. `backend/app/routers/repos.py`:
   - Router with prefix `/api/repos`, tags `["repos"]`
   - All endpoints require `Depends(get_current_user)` and `Depends(get_db)`

   - `POST /`:
     - Body: CreateRepoRequest
     - Call `create_or_get_repo(db, current_user.id, req.url)`
     - Return `{"success": true, "data": RepoResponse}`

   - `GET /`:
     - Call `list_repos(db, current_user.id)`
     - Map results to RepoResponse objects
     - Return `{"success": true, "data": [RepoResponse, ...]}`

   - `GET /{repo_id}`:
     - Call `get_repo(db, current_user.id, repo_id)`
     - Return `{"success": true, "data": RepoResponse}` (with scan_count=0 for now)

4. MODIFY `backend/app/main.py` — add:
   ```python
   from app.routers import repos
   app.include_router(repos.router)
   ```

CODING STYLE:
- Async handlers, select() queries, Depends() injection
- Response envelope on every endpoint
- Defensive: check ownership on every get/update
- RepoResponse scan_count will be 0 until Phase 3 adds the Scan model

CONSTRAINTS:
- Do NOT create any scan-related logic
- The list_repos function has a graceful fallback for when the Scan model doesn't exist yet
```

## Prompt 2.3 — Git Operations (Clone + File Discovery)

```
ROLE: You are implementing git operations for the ZeroPath scanner.

CONTEXT:
The backend has:
- `backend/app/scanner/__init__.py` — empty
- `backend/app/config.py` — settings.scan_workdir (default "/tmp/zeropath-scans")
- GitPython is in requirements.txt

TASK:
Create the git operations module with repo cloning and Python file discovery.

CREATE:

1. `backend/app/scanner/git_ops.py`:
   ```python
   import logging
   from pathlib import Path
   import git

   logger = logging.getLogger(__name__)

   SKIP_DIRS = {
       ".git", "venv", "env", ".venv", "node_modules", "__pycache__",
       ".tox", ".eggs", "site-packages", ".mypy_cache", ".pytest_cache",
       "dist", "build", ".egg-info",
   }


   def clone_repo(url: str, dest: Path, github_token: str | None = None) -> str:
       """Clone a git repo to dest directory (shallow). Returns commit SHA."""
       logger.info("[Scanner] Cloning %s to %s (authenticated: %s)", url, dest, bool(github_token))

       clone_url = url
       if github_token and "github.com" in url:
           clone_url = url.replace("https://", f"https://{github_token}@")

       repo = git.Repo.clone_from(
           clone_url,
           str(dest),
           depth=1,
           kill_after_timeout=120,
       )
       sha = repo.head.commit.hexsha
       logger.info("[Scanner] Cloned successfully, HEAD at %s", sha[:7])
       return sha


   def discover_python_files(repo_path: Path) -> list[Path]:
       """Walk repo and return relative paths to all .py files, skipping irrelevant dirs."""
       py_files = []

       for path in repo_path.rglob("*.py"):
           # Check if any parent directory should be skipped
           parts = path.relative_to(repo_path).parts
           if any(part in SKIP_DIRS for part in parts):
               continue
           py_files.append(path.relative_to(repo_path))

       py_files.sort()
       logger.info("[Scanner] Discovered %d Python files", len(py_files))
       return py_files
   ```

CODING STYLE:
- Standard library logging, not print()
- `[Scanner]` prefix on all log messages
- Function signatures include type hints
- `github_token` param is forward-looking for Phase 8 (private repos) — currently always None

CONSTRAINTS:
- Do NOT create the chunker, analyzer, or prompts — those are Phase 3
- clone_repo uses depth=1 (shallow clone) to save time and disk
- discover_python_files returns paths RELATIVE to repo_path
```

## Prompt 2.4 — Frontend Dashboard + Repo Detail

```
ROLE: You are implementing the dashboard and repository detail pages for ZeroPath Security Scanner.

CONTEXT:
The frontend has:
- `frontend/lib/api.ts` — `apiFetch<T>(endpoint, options)` returning `ApiResponse<T>`
- `frontend/lib/auth.ts` — `getAccessToken()`, `clearTokens()`
- `frontend/app/login/page.tsx` and `frontend/app/signup/page.tsx` — auth pages
- `frontend/app/page.tsx` — redirects to /dashboard or /login based on auth

Backend endpoints:
- `GET /api/repos` → `{success: true, data: [{id, url, name, scan_count, created_at, updated_at}, ...]}`
- `POST /api/repos` body: `{url}` → `{success: true, data: {id, url, name, scan_count, created_at, updated_at}}`
- `GET /api/repos/:id` → `{success: true, data: {id, url, name, scan_count, created_at, updated_at}}`
- `GET /api/auth/me` → `{success: true, data: {id, email, created_at}}`

TASK:
Create the NavHeader component, dashboard page (repo list + add form), and repo detail page.

CREATE:

1. `frontend/app/components/NavHeader.tsx`:
   - Named export `NavHeader`
   - `"use client"` directive
   - Sticky top bar: `bg-gray-900 text-white px-6 py-3 flex items-center justify-between sticky top-0 z-50`
   - Left: "ZeroPath" text (font-bold text-lg), links to `/dashboard`
   - Right: placeholder for user info (will be completed in Phase 7)
   - Use `next/link` for navigation

2. `frontend/app/dashboard/page.tsx`:
   - `"use client"` directive
   - Interfaces:
     ```typescript
     interface Repo {
       id: string;
       url: string;
       name: string;
       scan_count: number;
       created_at: string;
       updated_at: string;
     }
     ```
   - State: `repos` (Repo[]), `loading` (boolean), `url` (string), `addError` (string), `addLoading` (boolean)
   - Auth guard: `useEffect` checks `getAccessToken()`, redirects to `/login` if null
   - On mount: fetch `GET /api/repos`, populate repos
   - Layout:
     - `<NavHeader />` at top
     - `max-w-4xl mx-auto px-4 py-8` container
     - "Your Repositories" heading
     - Add repo form: text input for URL + "Add Repository" button in a row
       - Input placeholder: "https://github.com/owner/repo"
       - On submit: POST /api/repos, prepend to repos on success, show addError on failure
     - Repo list: cards in a vertical stack (gap-4)
       - Each card: `bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow cursor-pointer`
       - Shows: repo name (font-medium), URL (text-sm text-gray-500), scan count badge, created date
       - Wrapped in `next/link` to `/repos/{repo.id}`
     - Loading state: 3 skeleton cards with `animate-pulse bg-gray-200 rounded-lg h-20`
     - Empty state: "No repositories yet. Add a Git repository URL above to get started."

3. `frontend/app/repos/[id]/page.tsx`:
   - `"use client"`, auth guard, `useParams()` for id
   - Fetch `GET /api/repos/${id}` on mount
   - State: `repo` (Repo | null), `loading` (boolean), `error` (string)
   - Layout:
     - `<NavHeader />` at top
     - `max-w-4xl mx-auto px-4 py-8` container
     - Back link: `← Back to Dashboard` → `/dashboard`
     - Repo name as heading, URL as clickable link (opens in new tab)
     - Created date and scan count
     - Placeholder section: "Scan history will appear here after Phase 4."
   - Loading state: skeleton
   - Error state: red box with error message

CODING STYLE:
- `"use client"` on all three files
- Named export for NavHeader, default export for pages
- Tailwind utility classes for all styling
- `useRouter` from `next/navigation` for redirects
- `useParams` from `next/navigation` for dynamic route params
- Format dates with `new Date(dateStr).toLocaleDateString()`

CONSTRAINTS:
- Do NOT create scan-related UI — that's Phase 4
- Repo detail page has a placeholder where scan history will go
- NavHeader right side is a placeholder — Phase 7 adds user email + logout
```

---

**Verification after Phase 2:**
1. `POST /api/repos` with `{"url": "https://github.com/pallets/flask"}` → creates repo named `pallets/flask`
2. Same URL again → returns existing repo
3. `GET /api/repos` → lists repos for the authenticated user
4. Dashboard renders repo list and "Add Repository" form works
5. Clicking a repo card navigates to `/repos/{id}`
6. `clone_repo` + `discover_python_files` work on a real repo
