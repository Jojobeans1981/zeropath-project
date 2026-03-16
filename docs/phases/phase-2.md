# Phase 2: Repository Management & Git Operations

## Objective
Users can submit Git repo URLs, persist them, and the system can clone repos and discover Python files — the prerequisite for scanning.

## Current State (After Phase 1)
- **Backend:** FastAPI app with auth system. Endpoints: `GET /api/health`, `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me`. User model in DB. `get_current_user` dependency for protected routes. Auth service with JWT + bcrypt.
- **Frontend:** Next.js app with login/signup pages, `apiFetch<T>()` wrapper, auth utilities. Root page redirects based on auth state.
- **Database:** SQLite with `users` table.
- **Key files:** `backend/app/models/user.py`, `backend/app/schemas/auth.py`, `backend/app/routers/auth.py`, `backend/app/services/auth_service.py`, `backend/app/deps.py` (has `get_current_user`, `get_db`), `frontend/lib/api.ts`, `frontend/lib/auth.ts`

## Architecture Context

### API Response Envelope
```json
{ "success": true, "data": { ... } }
{ "success": false, "error": { "code": "...", "message": "..." } }
```

### Data Model: Repository
```
Repository
├── id: UUID (PK)
├── user_id: UUID (FK → users.id, indexed)
├── url: string (not null)
├── name: string (not null, extracted from URL e.g. "owner/repo")
├── created_at: datetime (UTC)
├── updated_at: datetime (UTC, auto-updates)
└── UNIQUE constraint on (user_id, url)
```

### API Endpoints
| Method | Path | Auth | Request Body | Response Data |
|--------|------|------|-------------|---------------|
| POST | `/api/repos` | Yes | `{ url: string }` | Repo object |
| GET | `/api/repos` | Yes | — | Array of repo objects with `scan_count` |
| GET | `/api/repos/:id` | Yes | — | Repo detail |

Repo object shape:
```json
{
  "id": "uuid",
  "url": "https://github.com/owner/repo",
  "name": "owner/repo",
  "scan_count": 0,
  "created_at": "2026-03-16T00:00:00Z",
  "updated_at": "2026-03-16T00:00:00Z"
}
```

## Coding Standards

### Python Backend
- File naming: lowercase snake_case
- Class naming: PascalCase
- All handlers and DB ops: `async def`
- Logging: `[Repo]` prefix for repo service, `[Scanner]` prefix for git_ops
- Comments: minimal, WHY not WHAT

### TypeScript Frontend
- `"use client"` on interactive pages
- Interfaces at top of file, no `any`
- `useState` for state, `apiFetch<T>()` for API calls
- Auth guard in `useEffect`: check token, redirect if missing
- Loading skeletons with `animate-pulse`
- Tailwind utility classes

## Deliverables

1. **`backend/app/models/repository.py`** — Repository SQLAlchemy model
2. **Alembic migration** — creates `repositories` table
3. **`backend/app/schemas/repo.py`** — Pydantic request/response models
4. **`backend/app/services/repo_service.py`** — Repository CRUD operations
5. **`backend/app/routers/repos.py`** — three repo endpoints
6. **`backend/app/scanner/git_ops.py`** — clone_repo + discover_python_files
7. **`frontend/app/dashboard/page.tsx`** — repo list + add repo form
8. **`frontend/app/repos/[id]/page.tsx`** — repo detail page
9. **`frontend/app/components/NavHeader.tsx`** — navigation header component

## Technical Specification

### backend/app/models/repository.py
- Table name: `repositories`
- Columns: `id` (UUID, default uuid4, PK), `user_id` (UUID, ForeignKey `users.id`, indexed, not null), `url` (String, not null), `name` (String, not null), `created_at` (DateTime, default utcnow), `updated_at` (DateTime, default utcnow, onupdate utcnow)
- `__table_args__` = `(UniqueConstraint("user_id", "url", name="uq_user_repo"),)`
- Relationship: `user = relationship("User", backref="repositories")`

### backend/app/schemas/repo.py
- `CreateRepoRequest(BaseModel)`: `url: str` — must start with `https://github.com/` or `https://gitlab.com/`
- `RepoResponse(BaseModel)`: `id: str`, `url: str`, `name: str`, `scan_count: int`, `created_at: datetime`, `updated_at: datetime`
- Validator on `url`: strip trailing `.git` and `/`, validate format

### backend/app/services/repo_service.py
- `create_or_get_repo(db, user_id, url) -> Repository`: Extract name from URL (split by `/`, take last two segments as `owner/repo`). Check if repo with same user_id + url exists. If yes, return it. If no, create and return.
- `list_repos(db, user_id) -> list[RepoResponse]`: Query repos for user, include scan count via subquery or join.
- `get_repo(db, user_id, repo_id) -> Repository`: Get repo by ID, verify it belongs to user. Raise 404 if not found, 403 if wrong user.

### backend/app/routers/repos.py
- Router prefix: `/api/repos`
- All endpoints require `Depends(get_current_user)`
- `POST /`: call `create_or_get_repo`, return wrapped in `{ success: true, data: RepoResponse }`
- `GET /`: call `list_repos`, return wrapped array
- `GET /{repo_id}`: call `get_repo`, return wrapped

### backend/app/scanner/git_ops.py
- `clone_repo(url: str, dest: Path) -> str`:
  - Uses `git.Repo.clone_from(url, str(dest), depth=1)` from GitPython
  - Returns `repo.head.commit.hexsha`
  - Timeout: set `GIT_HTTP_TIMEOUT` env or use GitPython's `kill_after_timeout=60`
  - Log: `[Scanner] Cloning {url} to {dest}`
  - On failure: log error, raise

- `discover_python_files(repo_path: Path) -> list[Path]`:
  - Walk `repo_path` recursively
  - Yield files ending in `.py`
  - Skip directories named: `.git`, `venv`, `env`, `.venv`, `node_modules`, `__pycache__`, `.tox`, `.eggs`, `site-packages`, `.mypy_cache`, `.pytest_cache`
  - Return paths relative to `repo_path`
  - Log: `[Scanner] Discovered {len(files)} Python files`

### frontend/app/components/NavHeader.tsx
- Named export: `NavHeader`
- Props: none (reads auth state internally)
- Shows "ZeroPath" logo/text on left
- Shows user context on right (placeholder for now — will add email + logout in Phase 7)
- Sticky top bar with dark background (Tailwind: `bg-gray-900 text-white`)
- Links: "Dashboard" → `/dashboard`

### frontend/app/dashboard/page.tsx
- `"use client"`, auth guard in `useEffect`
- Interfaces: `Repo { id: string; url: string; name: string; scan_count: number; created_at: string }`
- State: `repos` (Repo[]), `loading` (boolean), `url` (string for add form), `addError` (string), `addLoading` (boolean)
- On mount: fetch `GET /api/repos`, populate repos list
- "Add Repository" section: text input for URL, submit button. On submit: `POST /api/repos` with `{ url }`. On success: prepend to repos list, clear input. On error: show error.
- Repo list: cards showing repo name, URL, scan count, created date. Each card links to `/repos/{id}`.
- Empty state: "No repositories yet. Add one above to get started."
- Loading state: 3 skeleton cards with `animate-pulse`
- Includes `<NavHeader />` at top

### frontend/app/repos/[id]/page.tsx
- `"use client"`, auth guard, `useParams()` to get `id`
- Fetch `GET /api/repos/{id}` on mount
- Display: repo name (heading), URL (link), created date
- Placeholder text: "Scan history will appear here" (built in Phase 4)
- Back link to `/dashboard`
- Includes `<NavHeader />` at top

## Acceptance Criteria

1. `POST /api/repos` with `{ url: "https://github.com/pallets/flask" }` creates repo with name `pallets/flask` and returns it
2. `POST /api/repos` with the same URL for the same user returns the existing repo (no duplicate created)
3. `POST /api/repos` with invalid URL format returns 422 validation error
4. `GET /api/repos` returns only the authenticated user's repos
5. `GET /api/repos/:id` for another user's repo returns 403
6. `clone_repo("https://github.com/pallets/click", dest)` clones successfully and returns a 40-char hex SHA
7. `discover_python_files(cloned_path)` returns `.py` files and excludes `venv/`, `__pycache__/`, etc.
8. Dashboard page lists repos and allows adding new ones via the form
9. Clicking a repo card navigates to `/repos/{id}` detail page
10. NavHeader renders on both pages
