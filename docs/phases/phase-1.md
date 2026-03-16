# Phase 1: Authentication System

## Objective
Implement user signup, login, JWT token management, and protected routes — the foundation for all user-scoped data.

## Current State (After Phase 0)
- **Backend:** FastAPI app with `GET /api/health`, CORS configured, SQLAlchemy async engine + Alembic, Celery worker with Redis, Pydantic Settings config
- **Frontend:** Next.js 14 app with `apiFetch<T>()` wrapper in `lib/api.ts`, auth utilities in `lib/auth.ts` (`getAccessToken`, `setTokens`, `clearTokens`), Tailwind CSS, placeholder page
- **Database:** SQLite via aiosqlite, empty schema
- **Files exist:** `backend/app/main.py`, `backend/app/config.py`, `backend/app/database.py`, `backend/app/deps.py` (empty), `frontend/lib/api.ts`, `frontend/lib/auth.ts`

## Architecture Context

### API Response Envelope (all endpoints)
```json
// Success
{ "success": true, "data": { ... } }

// Error
{ "success": false, "error": { "code": "ERROR_CODE", "message": "Human-readable message" } }
```

### Data Model: User
```
User
├── id: UUID (PK, server-generated via uuid4)
├── email: string (unique, indexed)
├── password_hash: string
├── created_at: datetime (server-generated, UTC)
└── updated_at: datetime (server-generated, UTC, auto-updates)
```

### API Endpoints
| Method | Path | Auth Required | Request Body | Response Data |
|--------|------|---------------|-------------|---------------|
| POST | `/api/auth/signup` | No | `{ email: string, password: string }` | `{ access_token: string, refresh_token: string, token_type: "bearer" }` |
| POST | `/api/auth/login` | No | `{ email: string, password: string }` | `{ access_token: string, refresh_token: string, token_type: "bearer" }` |
| POST | `/api/auth/refresh` | No | `{ refresh_token: string }` | `{ access_token: string, token_type: "bearer" }` |
| GET | `/api/auth/me` | Yes (Bearer) | — | `{ id: string, email: string, created_at: string }` |

### JWT Configuration
- Algorithm: HS256
- Access token TTL: 30 minutes (configurable via `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh token TTL: 7 days (configurable via `JWT_REFRESH_TOKEN_EXPIRE_DAYS`)
- Token payload: `{ "sub": "<user_uuid>", "exp": <unix_timestamp> }`
- Secret key: `JWT_SECRET` env var

## Coding Standards

### Python Backend
- File naming: lowercase snake_case
- Class naming: PascalCase
- All route handlers and DB operations: `async def`
- Logging: `[Auth]` prefixed messages
- Error handling: `HTTPException` with structured error codes
- Password hashing: `passlib` with bcrypt scheme
- JWT: `python-jose` with HS256

### TypeScript Frontend
- `"use client"` on interactive pages
- Interfaces at top of file, no `any`
- `useState` for form state and errors
- `apiFetch<T>()` for all API calls
- Token storage via `setTokens()` / `clearTokens()` from `lib/auth.ts`
- Error messages rendered below forms in red text
- Loading state: disabled button with "Loading..." text
- Auth guard: `useEffect` checks `getAccessToken()`, redirects to `/login` if null

## Deliverables

1. **`backend/app/models/user.py`** — User SQLAlchemy model
2. **Alembic migration** — creates `users` table
3. **`backend/app/schemas/auth.py`** — Pydantic request/response models
4. **`backend/app/services/auth_service.py`** — password hashing, JWT creation/validation
5. **`backend/app/routers/auth.py`** — four auth endpoints
6. **`backend/app/deps.py`** — `get_current_user` dependency
7. **`frontend/app/login/page.tsx`** — login form
8. **`frontend/app/signup/page.tsx`** — signup form
9. **`frontend/app/page.tsx`** — updated to redirect based on auth state

## Technical Specification

### backend/app/models/user.py
- SQLAlchemy model inheriting from `Base` (from `database.py`)
- Table name: `users`
- Columns: `id` (UUID, default `uuid4`, primary key), `email` (String, unique, indexed, not null), `password_hash` (String, not null), `created_at` (DateTime, default `utcnow`), `updated_at` (DateTime, default `utcnow`, `onupdate=utcnow`)

### backend/app/models/__init__.py
- Import `User` so Alembic autogenerate can discover it

### backend/app/schemas/auth.py
- `SignupRequest(BaseModel)`: `email: EmailStr`, `password: str` (min_length=8)
- `LoginRequest(BaseModel)`: `email: EmailStr`, `password: str`
- `RefreshRequest(BaseModel)`: `refresh_token: str`
- `TokenResponse(BaseModel)`: `access_token: str`, `refresh_token: str`, `token_type: str = "bearer"`
- `AccessTokenResponse(BaseModel)`: `access_token: str`, `token_type: str = "bearer"`
- `UserResponse(BaseModel)`: `id: str`, `email: str`, `created_at: datetime`

### backend/app/services/auth_service.py
- `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")`
- `hash_password(password: str) -> str`
- `verify_password(plain: str, hashed: str) -> bool`
- `create_access_token(user_id: str) -> str` — encodes `{ "sub": user_id, "exp": now + access_ttl }` with `JWT_SECRET`
- `create_refresh_token(user_id: str) -> str` — encodes `{ "sub": user_id, "exp": now + refresh_ttl }` with `JWT_SECRET`
- `decode_token(token: str) -> str` — decodes token, returns `sub` (user_id). Raises `HTTPException(401)` on expired/invalid.

### backend/app/routers/auth.py
- Router prefix: `/api/auth`
- `POST /signup`:
  1. Check if email already exists → 409 `{ code: "EMAIL_EXISTS", message: "An account with this email already exists." }`
  2. Hash password, create User record
  3. Generate tokens, return `TokenResponse`
- `POST /login`:
  1. Find user by email → 401 `{ code: "INVALID_CREDENTIALS", message: "Invalid email or password." }` if not found
  2. Verify password → same 401 if wrong (don't reveal which field is wrong)
  3. Generate tokens, return `TokenResponse`
- `POST /refresh`:
  1. Decode refresh token → 401 if invalid/expired
  2. Verify user still exists → 401 if deleted
  3. Generate new access token only, return `AccessTokenResponse`
- `GET /me`:
  1. Requires `Depends(get_current_user)`
  2. Return `UserResponse`

### backend/app/deps.py
- `get_db()` — async generator yielding `AsyncSession` (move from `database.py` or re-export)
- `get_current_user(token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)) -> User`
  - `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")`
  - Decode token via `auth_service.decode_token()`
  - Query user by ID
  - Return User or raise 401

### backend/app/main.py (modify)
- Add `from app.routers import auth`
- Include router: `app.include_router(auth.router)`

### frontend/app/login/page.tsx
- `"use client"` directive
- Interfaces: `LoginForm { email: string; password: string }`
- State: `form` (LoginForm), `error` (string), `loading` (boolean)
- On submit: call `apiFetch<{ access_token: string; refresh_token: string }>("/api/auth/login", { method: "POST", body: JSON.stringify(form) })`
- On success: `setTokens(data.access_token, data.refresh_token)`, `router.push("/dashboard")`
- On error: `setError(res.error?.message || "Login failed.")`
- Link to `/signup` at bottom
- Centered card layout with Tailwind

### frontend/app/signup/page.tsx
- Same pattern as login, but with confirm password field
- Client-side validation: passwords must match
- Calls `POST /api/auth/signup`
- Link to `/login` at bottom

### frontend/app/page.tsx (modify)
- `"use client"` directive
- `useEffect`: if `getAccessToken()` exists → `router.replace("/dashboard")`, else → `router.replace("/login")`
- Render loading state while redirecting

## Acceptance Criteria

1. `POST /api/auth/signup` with `{ email: "test@example.com", password: "password123" }` returns 200 with tokens
2. `POST /api/auth/signup` with same email returns 409 with `EMAIL_EXISTS` error code
3. `POST /api/auth/login` with correct credentials returns 200 with tokens
4. `POST /api/auth/login` with wrong password returns 401 with `INVALID_CREDENTIALS`
5. `GET /api/auth/me` with valid Bearer token returns user data (id, email, created_at)
6. `GET /api/auth/me` without token returns 401
7. `POST /api/auth/refresh` with valid refresh token returns new access token
8. Frontend login form: submitting valid credentials stores tokens and redirects to `/dashboard`
9. Frontend signup form: submitting valid data creates account and redirects to `/dashboard`
10. Navigating to `/` redirects to `/login` when no token exists
11. Navigating to `/` redirects to `/dashboard` when token exists
