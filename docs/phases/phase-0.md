# Phase 0: Project Scaffolding

## Objective
Set up the monorepo structure, install all dependencies, configure dev tooling, and verify both servers run — zero business logic.

## Current State
Nothing exists. Starting from an empty directory.

## Architecture Context

### System Overview
This project is a monorepo with two applications:
- **backend/** — Python FastAPI REST API + Celery worker for background task processing
- **frontend/** — Next.js 14 TypeScript app with Tailwind CSS

They communicate via REST API calls. A Redis instance serves as the Celery task broker.

### Stack
- **Backend:** Python 3.11+, FastAPI ^0.115, Uvicorn ^0.34, SQLAlchemy ^2.0 (async, aiosqlite), Alembic ^1.14, Celery ^5.4, Redis ^5.0, python-jose[cryptography] ^3.3, passlib[bcrypt] ^1.7, GitPython ^3.1, anthropic ^0.52, pydantic ^2.0, pydantic-settings ^2.0, httpx ^0.28, pytest ^8.0, pytest-asyncio ^0.24
- **Frontend:** Next.js ^14.2, React ^18, Tailwind CSS ^3.4, @heroicons/react ^2.2
- **Infrastructure:** Redis (via Docker Compose), SQLite (file-based)

## Coding Standards

### Python Backend
- File naming: lowercase snake_case (`scan_service.py`)
- Class naming: PascalCase
- All route handlers and DB operations: `async def`
- Logging: `[Stage]` prefixed messages (e.g. `[Worker] Starting scan...`)
- Comments: minimal — explain WHY not WHAT
- Config: environment variables via `pydantic-settings`, never hardcoded secrets

### TypeScript Frontend
- `"use client"` directive on all interactive pages
- Interfaces defined at top of file, no `any` types
- `useState` for local state, no global state library
- Centralized `apiFetch<T>()` wrapper returning `{ success: boolean, data?: T, error?: { code: string, message: string } }`
- Token storage in `localStorage` via `getAccessToken()`, `setTokens()`, `clearTokens()`
- Tailwind utility classes for styling
- Named exports for components, default exports for pages

## Deliverables

1. **Backend FastAPI app** returning `{ "status": "ok" }` at `GET /api/health`
2. **Frontend Next.js app** rendering a placeholder page at `http://localhost:3000`
3. **`docker-compose.yml`** with Redis service on port 6379
4. **SQLAlchemy async engine** + Alembic migration config (empty schema, no tables yet)
5. **Celery worker** connecting to Redis, processing a no-op test task
6. **`apiFetch<T>()`** wrapper in `frontend/lib/api.ts`
7. **Auth utilities** in `frontend/lib/auth.ts`: `getAccessToken()`, `setTokens(access, refresh)`, `clearTokens()`
8. **`.env.example`** documenting all required environment variables
9. **`.gitignore`** for Python, Node, and environment files

## Technical Specification

### File Structure to Create

```
zeropath/
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── backend/
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/          # empty directory
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # FastAPI app, CORS, health endpoint
│   │   ├── config.py          # Pydantic Settings class
│   │   ├── database.py        # Async SQLAlchemy engine + session factory
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── schemas/
│   │   │   └── __init__.py
│   │   ├── routers/
│   │   │   └── __init__.py
│   │   ├── services/
│   │   │   └── __init__.py
│   │   ├── scanner/
│   │   │   └── __init__.py
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   └── scan_worker.py # Celery app + test task
│   │   └── deps.py            # Empty for now, will hold auth deps
│   └── tests/
│       └── __init__.py
│
└── frontend/
    ├── package.json
    ├── tsconfig.json
    ├── next.config.mjs
    ├── tailwind.config.js
    ├── postcss.config.mjs
    ├── lib/
    │   ├── api.ts
    │   └── auth.ts
    └── app/
        ├── layout.tsx
        ├── page.tsx
        └── globals.css
```

### Backend Details

**`app/config.py`** — Pydantic Settings class:
```python
class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./zeropath.db"
    anthropic_api_key: str
    jwt_secret: str
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7
    redis_url: str = "redis://localhost:6379/0"
    scan_workdir: str = "/tmp/zeropath-scans"
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env")
```

**`app/database.py`** — Async SQLAlchemy:
- `engine = create_async_engine(settings.database_url)`
- `async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
- `Base = declarative_base()` for model inheritance
- `async def get_db()` — async generator yielding sessions for FastAPI `Depends()`

**`app/main.py`** — FastAPI app:
- `CORSMiddleware` allowing origins from `settings.cors_origins` (split by comma)
- `GET /api/health` → `{ "status": "ok" }`
- No routers included yet

**`workers/scan_worker.py`** — Celery app:
- `celery_app = Celery("zeropath", broker=settings.redis_url)`
- One test task: `@celery_app.task def test_task(): return "ok"`

**`alembic.ini` + `alembic/env.py`:**
- `sqlalchemy.url` reads from `DATABASE_URL` env var
- `env.py` imports `Base.metadata` from `app.database` for autogenerate support
- Target metadata set for future model autogeneration

### Frontend Details

**`lib/api.ts`** — Centralized fetch wrapper:
```typescript
interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>>
```
- Prepends `process.env.NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
- Injects `Authorization: Bearer <token>` if token exists in localStorage
- Sets `Content-Type: application/json` by default
- On 401 response: clears tokens, returns error
- On network error: returns `{ success: false, error: { code: "NETWORK_ERROR", message } }`

**`lib/auth.ts`** — Token management:
```typescript
export function getAccessToken(): string | null
export function getRefreshToken(): string | null
export function setTokens(access: string, refresh: string): void
export function clearTokens(): void
```
All operate on `localStorage` keys `access_token` and `refresh_token`.

**`app/layout.tsx`** — Root layout with HTML structure, font imports, metadata (`title: "ZeroPath"`)

**`app/page.tsx`** — Simple placeholder: "ZeroPath Security Scanner" heading

**`app/globals.css`** — Tailwind directives (`@tailwind base; @tailwind components; @tailwind utilities;`)

### Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

### Environment Variables (`.env.example`)

```bash
# Backend
DATABASE_URL=sqlite+aiosqlite:///./zeropath.db
ANTHROPIC_API_KEY=sk-ant-your-key-here
JWT_SECRET=change-this-to-a-random-32-char-string
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7
REDIS_URL=redis://localhost:6379/0
SCAN_WORKDIR=/tmp/zeropath-scans
CORS_ORIGINS=http://localhost:3000

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Acceptance Criteria

1. `cd backend && uvicorn app.main:app --reload` starts and `GET http://localhost:8000/api/health` returns `{ "status": "ok" }` with status 200
2. `cd frontend && npm run dev` starts and renders at `http://localhost:3000`
3. `docker compose up redis` starts Redis on port 6379
4. `cd backend && celery -A app.workers.scan_worker worker --loglevel=info` starts without errors
5. `alembic revision --autogenerate -m "init"` generates an empty migration
6. `alembic upgrade head` applies without errors
7. `.env.example` lists all 8 backend env vars and 1 frontend env var
8. `.gitignore` excludes: `__pycache__`, `.env`, `node_modules`, `.next`, `*.db`, `venv/`
