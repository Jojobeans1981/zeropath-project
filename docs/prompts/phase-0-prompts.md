# Phase 0: Project Scaffolding — Implementation Prompts

## Prompt 0.1 — Root Config Files

```
ROLE: You are setting up the root configuration for a monorepo called "ZeroPath Security Scanner".

TASK:
Create the root-level configuration files for the project. The project is a monorepo with a Python backend (backend/) and a Next.js frontend (frontend/).

CREATE the following files in the project root:

1. `.gitignore` — Include rules for:
   - Python: __pycache__/, *.pyc, *.pyo, venv/, .venv/, *.egg-info/, dist/, build/, .tox/, .eggs/, site-packages/, .mypy_cache/, .pytest_cache/
   - Node: node_modules/, .next/, out/
   - Environment: .env, .env.local, .env.*.local
   - Database: *.db, *.sqlite3
   - OS: .DS_Store, Thumbs.db
   - IDE: .vscode/, .idea/

2. `.env.example` — Document all required environment variables:
   ```
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

3. `docker-compose.yml` — Single service for now:
   ```yaml
   services:
     redis:
       image: redis:7-alpine
       ports:
         - "6379:6379"
   ```

CODING STYLE:
- YAML: 2-space indentation
- Comments: minimal, only where the value needs explanation

CONSTRAINTS:
- Do NOT create any application code yet — only root config files
- Do NOT add services for the backend or frontend to docker-compose (they run locally for dev)
```

## Prompt 0.2 — Backend Scaffolding

```
ROLE: You are setting up the Python FastAPI backend for ZeroPath Security Scanner.

CONTEXT:
The project root exists with .gitignore, .env.example, and docker-compose.yml. You are now creating the backend/ directory.

TASK:
Create the backend directory structure and install configuration. Do NOT write any application logic yet — just the skeleton.

CREATE the following files:

1. `backend/requirements.txt`:
   ```
   fastapi==0.115.6
   uvicorn[standard]==0.34.0
   sqlalchemy[asyncio]==2.0.36
   aiosqlite==0.20.0
   alembic==1.14.0
   celery==5.4.0
   redis==5.2.1
   python-jose[cryptography]==3.3.0
   passlib[bcrypt]==1.7.4
   email-validator==2.2.0
   gitpython==3.1.43
   anthropic==0.52.0
   pydantic==2.10.3
   pydantic-settings==2.7.0
   httpx==0.28.1
   pytest==8.3.4
   pytest-asyncio==0.24.0
   ```

2. `backend/app/__init__.py` — empty file

3. `backend/app/config.py`:
   ```python
   from pydantic_settings import BaseSettings, SettingsConfigDict


   class Settings(BaseSettings):
       database_url: str = "sqlite+aiosqlite:///./zeropath.db"
       anthropic_api_key: str = ""
       jwt_secret: str = "change-me"
       jwt_access_token_expire_minutes: int = 30
       jwt_refresh_token_expire_days: int = 7
       redis_url: str = "redis://localhost:6379/0"
       scan_workdir: str = "/tmp/zeropath-scans"
       cors_origins: str = "http://localhost:3000"

       model_config = SettingsConfigDict(env_file=".env")


   settings = Settings()
   ```

4. Create empty `__init__.py` files in each of these directories (create the directories too):
   - `backend/app/models/`
   - `backend/app/schemas/`
   - `backend/app/routers/`
   - `backend/app/services/`
   - `backend/app/scanner/`
   - `backend/app/workers/`
   - `backend/tests/`

CODING STYLE:
- File naming: lowercase snake_case
- Imports: standard library first, third-party second, local third, separated by blank lines
- All __init__.py files should be empty (no imports yet)

CONSTRAINTS:
- Do NOT create main.py, database.py, or any application logic yet — those are in the next prompt
- Do NOT run pip install — just create the requirements.txt
```

## Prompt 0.3 — Backend Core (FastAPI App + Database + Celery)

```
ROLE: You are building the core backend application files for ZeroPath Security Scanner.

CONTEXT:
The backend/ directory exists with:
- `backend/requirements.txt` — all dependencies listed
- `backend/app/__init__.py` — empty
- `backend/app/config.py` — Settings class with all env vars, exports `settings` singleton
- Empty `__init__.py` in: models/, schemas/, routers/, services/, scanner/, workers/, tests/

The Settings class has these fields: database_url, anthropic_api_key, jwt_secret, jwt_access_token_expire_minutes, jwt_refresh_token_expire_days, redis_url, scan_workdir, cors_origins.

TASK:
Create the core application files: FastAPI app, async database engine, Alembic config, Celery worker, and dependency injection helpers.

CREATE the following files:

1. `backend/app/database.py`:
   - Import `create_async_engine`, `async_sessionmaker`, `AsyncSession` from sqlalchemy.ext.asyncio
   - Import `create_engine`, `sessionmaker` from sqlalchemy (for sync Celery worker)
   - Import `declarative_base` from sqlalchemy.orm
   - Import `settings` from `app.config`
   - Create: `Base = declarative_base()`
   - Create async engine: `engine = create_async_engine(settings.database_url, echo=False)`
   - Create async session factory: `async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`
   - Create sync engine (for Celery): `sync_engine = create_engine(settings.database_url.replace("+aiosqlite", ""), echo=False)`
   - Create sync session factory: `SyncSessionLocal = sessionmaker(bind=sync_engine)`
   - Create `async def get_db()` generator: yields an AsyncSession, used with FastAPI Depends()

2. `backend/app/main.py`:
   - Import FastAPI, CORSMiddleware
   - Import `settings` from `app.config`
   - Create FastAPI app: `app = FastAPI(title="ZeroPath Security Scanner", version="1.0.0")`
   - Add CORSMiddleware:
     - `allow_origins` = `settings.cors_origins.split(",")`
     - `allow_credentials` = True
     - `allow_methods` = ["*"]
     - `allow_headers` = ["*"]
   - Add health endpoint: `GET /api/health` returning `{"status": "ok"}`

3. `backend/app/deps.py`:
   - Import `get_db` from `app.database` and re-export it
   - Add a comment: `# Auth dependencies will be added in Phase 1`

4. `backend/app/workers/scan_worker.py`:
   - Import Celery
   - Import `settings` from `app.config`
   - Create Celery app: `celery_app = Celery("zeropath", broker=settings.redis_url)`
   - Configure: `celery_app.conf.task_serializer = "json"` and `celery_app.conf.result_serializer = "json"`
   - Add test task:
     ```python
     @celery_app.task
     def test_task():
         return "ok"
     ```

5. `backend/alembic.ini`:
   - Standard Alembic config
   - `sqlalchemy.url` = `sqlite:///./zeropath.db` (will be overridden by env.py)
   - `script_location` = `alembic`

6. `backend/alembic/env.py`:
   - Import `Base` from `app.database`
   - Set `target_metadata = Base.metadata`
   - Standard async Alembic env.py setup for SQLAlchemy async engine
   - Read database URL from environment variable `DATABASE_URL` with fallback to alembic.ini config

7. `backend/alembic/versions/` — empty directory (create a `.gitkeep` file)

CODING STYLE:
- All database operations use `async def`
- Logging: use `[Health]` prefix for health endpoint logs (if any)
- No unnecessary imports — only import what's used
- Comments: minimal, explain WHY not WHAT

CONSTRAINTS:
- Do NOT include any routers in main.py yet — no `app.include_router()` calls
- The health endpoint is the ONLY route
- Do NOT create any models — that happens in Phase 1
- The test_task in scan_worker is temporary — it gets replaced in Phase 3
```

## Prompt 0.4 — Frontend Scaffolding

```
ROLE: You are setting up the Next.js 14 frontend for ZeroPath Security Scanner.

CONTEXT:
The project root exists with .gitignore, .env.example, docker-compose.yml, and a complete backend/ directory. You are now creating the frontend/ directory.

TASK:
Initialize a Next.js 14 project with TypeScript and Tailwind CSS, plus the core utility files.

CREATE the following files:

1. `frontend/package.json`:
   ```json
   {
     "name": "zeropath-frontend",
     "version": "1.0.0",
     "private": true,
     "scripts": {
       "dev": "next dev",
       "build": "next build",
       "start": "next start",
       "lint": "next lint"
     },
     "dependencies": {
       "next": "^14.2.21",
       "react": "^18.3.1",
       "react-dom": "^18.3.1",
       "@heroicons/react": "^2.2.0"
     },
     "devDependencies": {
       "typescript": "^5.7.2",
       "@types/node": "^22.10.2",
       "@types/react": "^18.3.12",
       "@types/react-dom": "^18.3.1",
       "tailwindcss": "^3.4.17",
       "postcss": "^8.4.49",
       "autoprefixer": "^10.4.20"
     }
   }
   ```

2. `frontend/tsconfig.json` — Standard Next.js TypeScript config with strict mode, path aliases (`@/*` → `./app/*`, `@/lib/*` → `./lib/*`)

3. `frontend/next.config.mjs`:
   ```javascript
   /** @type {import('next').NextConfig} */
   const nextConfig = {};
   export default nextConfig;
   ```

4. `frontend/tailwind.config.js`:
   ```javascript
   /** @type {import('tailwindcss').Config} */
   module.exports = {
     content: [
       "./app/**/*.{js,ts,jsx,tsx}",
       "./lib/**/*.{js,ts,jsx,tsx}",
     ],
     theme: { extend: {} },
     plugins: [],
   };
   ```

5. `frontend/postcss.config.mjs`:
   ```javascript
   const config = {
     plugins: {
       tailwindcss: {},
       autoprefixer: {},
     },
   };
   export default config;
   ```

6. `frontend/app/globals.css`:
   ```css
   @tailwind base;
   @tailwind components;
   @tailwind utilities;
   ```

7. `frontend/app/layout.tsx`:
   - Root layout with `<html lang="en">` and `<body>` tags
   - Import `./globals.css`
   - Metadata: title "ZeroPath", description "LLM-Powered Security Scanner"
   - Use Inter font from `next/font/google`

8. `frontend/app/page.tsx`:
   - Simple placeholder page: centered "ZeroPath Security Scanner" heading
   - Subtitle: "Scan Python repositories for security vulnerabilities"
   - Tailwind styling: `min-h-screen flex items-center justify-center`

9. `frontend/lib/api.ts`:
   ```typescript
   const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

   interface ApiError {
     code: string;
     message: string;
   }

   interface ApiResponse<T> {
     success: boolean;
     data?: T;
     error?: ApiError;
   }

   export async function apiFetch<T>(
     endpoint: string,
     options: RequestInit = {}
   ): Promise<ApiResponse<T>> {
     const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

     const headers: HeadersInit = {
       "Content-Type": "application/json",
       ...options.headers,
     };

     if (token) {
       (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
     }

     try {
       const res = await fetch(`${API_URL}${endpoint}`, {
         ...options,
         headers,
       });

       const body = await res.json();

       if (!res.ok) {
         if (res.status === 401) {
           localStorage.removeItem("access_token");
           localStorage.removeItem("refresh_token");
         }
         return {
           success: false,
           error: body.error || body.detail || { code: "UNKNOWN", message: "An unexpected error occurred." },
         };
       }

       return { success: true, data: body.data !== undefined ? body.data : body };
     } catch (err) {
       return {
         success: false,
         error: { code: "NETWORK_ERROR", message: err instanceof Error ? err.message : "Network error" },
       };
     }
   }
   ```

10. `frontend/lib/auth.ts`:
    ```typescript
    export function getAccessToken(): string | null {
      if (typeof window === "undefined") return null;
      return localStorage.getItem("access_token");
    }

    export function getRefreshToken(): string | null {
      if (typeof window === "undefined") return null;
      return localStorage.getItem("refresh_token");
    }

    export function setTokens(access: string, refresh: string): void {
      localStorage.setItem("access_token", access);
      localStorage.setItem("refresh_token", refresh);
    }

    export function clearTokens(): void {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
    ```

CODING STYLE:
- TypeScript strict mode
- Named exports for utilities, default exports for pages
- Interfaces defined at top of file
- No `any` types
- Tailwind utility classes for all styling
- "use client" directive only on interactive pages (not layout)

CONSTRAINTS:
- Do NOT run npm install — just create the files
- Do NOT create any page besides the root placeholder
- The apiFetch wrapper handles the standard response envelope: { success, data/error }
- Token storage is in localStorage (not cookies) — simple for a take-home
```

---

**Verification after Phase 0:**
After all prompts are complete, verify:
1. `cd backend && pip install -r requirements.txt && uvicorn app.main:app --reload` → health endpoint returns `{"status": "ok"}`
2. `cd frontend && npm install && npm run dev` → renders placeholder page at localhost:3000
3. `docker compose up redis` → Redis on port 6379
4. `cd backend && celery -A app.workers.scan_worker worker --loglevel=info` → starts without errors
5. `cd backend && alembic revision --autogenerate -m "init"` → generates empty migration
