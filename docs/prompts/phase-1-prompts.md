# Phase 1: Authentication System — Implementation Prompts

## Prompt 1.1 — User Model + Migration

```
ROLE: You are implementing the User model and database migration for ZeroPath Security Scanner.

CONTEXT:
The backend exists with:
- `backend/app/database.py` — exports `Base` (declarative_base), `engine` (async), `async_session_maker`, `sync_engine`, `SyncSessionLocal`, `get_db()` async generator
- `backend/app/config.py` — exports `settings` with fields: database_url, jwt_secret, jwt_access_token_expire_minutes, jwt_refresh_token_expire_days, redis_url, etc.
- `backend/app/models/__init__.py` — empty
- Alembic configured in `backend/alembic/` with env.py importing `Base.metadata`

TASK:
Create the User model and generate the initial database migration.

CREATE:

1. `backend/app/models/user.py`:
   ```python
   import uuid
   from datetime import datetime, timezone
   from sqlalchemy import Column, String, DateTime
   from sqlalchemy.dialects.sqlite import CHAR
   from app.database import Base


   def utcnow():
       return datetime.now(timezone.utc)


   class User(Base):
       __tablename__ = "users"

       id = Column(CHAR(36), primary_key=True, default=lambda: str(uuid.uuid4()))
       email = Column(String, unique=True, index=True, nullable=False)
       password_hash = Column(String, nullable=False)
       created_at = Column(DateTime, default=utcnow)
       updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
   ```

2. MODIFY `backend/app/models/__init__.py`:
   ```python
   from app.models.user import User

   __all__ = ["User"]
   ```
   This import is required so Alembic autogenerate can discover the User model.

3. Run: `cd backend && alembic revision --autogenerate -m "create_users_table"` then `alembic upgrade head`

CODING STYLE:
- UUID stored as CHAR(36) string (SQLite doesn't have native UUID)
- `utcnow()` helper function defined in the model file (reused by future models)
- No relationships yet — those are added when related models are created

CONSTRAINTS:
- Do NOT create any other models — only User
- Do NOT modify main.py or add any routes
```

## Prompt 1.2 — Auth Schemas + Service

```
ROLE: You are implementing authentication schemas and the auth service for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/user.py` — User model with id (UUID string), email, password_hash, created_at, updated_at
- `backend/app/config.py` — settings with jwt_secret, jwt_access_token_expire_minutes (30), jwt_refresh_token_expire_days (7)
- Database with `users` table after migration

TASK:
Create Pydantic request/response schemas and the auth service with password hashing and JWT management.

CREATE:

1. `backend/app/schemas/auth.py`:
   ```python
   from datetime import datetime
   from pydantic import BaseModel, EmailStr


   class SignupRequest(BaseModel):
       email: EmailStr
       password: str  # min 8 chars validated in router

   class LoginRequest(BaseModel):
       email: EmailStr
       password: str

   class RefreshRequest(BaseModel):
       refresh_token: str

   class TokenResponse(BaseModel):
       access_token: str
       refresh_token: str
       token_type: str = "bearer"

   class AccessTokenResponse(BaseModel):
       access_token: str
       token_type: str = "bearer"

   class UserResponse(BaseModel):
       id: str
       email: str
       created_at: datetime
   ```

2. `backend/app/services/auth_service.py`:
   - Import: `passlib.context.CryptContext`, `jose.jwt`, `jose.JWTError`, `datetime`, `timedelta`
   - Import: `settings` from `app.config`, `HTTPException` from fastapi
   - `pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")`
   - `hash_password(password: str) -> str`: return `pwd_context.hash(password)`
   - `verify_password(plain: str, hashed: str) -> bool`: return `pwd_context.verify(plain, hashed)`
   - `create_access_token(user_id: str) -> str`:
     - payload: `{"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)}`
     - return `jwt.encode(payload, settings.jwt_secret, algorithm="HS256")`
   - `create_refresh_token(user_id: str) -> str`:
     - payload: `{"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)}`
     - return `jwt.encode(payload, settings.jwt_secret, algorithm="HS256")`
   - `decode_token(token: str) -> str`:
     - try: decode with `jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])`, return `payload["sub"]`
     - except JWTError or KeyError: raise `HTTPException(status_code=401, detail={"error": {"code": "INVALID_TOKEN", "message": "Invalid or expired token."}})`

CODING STYLE:
- All functions are plain (not async) — they don't do I/O
- No logging needed in auth service
- Import `timezone` from datetime for UTC-aware timestamps

CONSTRAINTS:
- Do NOT create routes — that's the next prompt
- Do NOT modify any existing files
```

## Prompt 1.3 — Auth Router + Dependencies

```
ROLE: You are implementing the auth API endpoints and dependency injection for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/user.py` — User model (id, email, password_hash, created_at, updated_at)
- `backend/app/schemas/auth.py` — SignupRequest, LoginRequest, RefreshRequest, TokenResponse, AccessTokenResponse, UserResponse
- `backend/app/services/auth_service.py` — hash_password(), verify_password(), create_access_token(), create_refresh_token(), decode_token()
- `backend/app/database.py` — get_db() yields AsyncSession
- `backend/app/deps.py` — currently only re-exports get_db
- `backend/app/main.py` — FastAPI app with CORS + health endpoint, no routers included

The API uses a response envelope:
- Success: `{"success": true, "data": {...}}`
- Error: `{"success": false, "error": {"code": "ERROR_CODE", "message": "Human-readable message."}}`

TASK:
Create the auth router with four endpoints, update deps.py with get_current_user, and register the router in main.py.

CREATE:

1. `backend/app/routers/auth.py`:
   - Router with prefix `/api/auth`, tags `["auth"]`

   - `POST /signup`:
     - Validate password length >= 8, return 422 if not
     - Check if email exists in DB (SELECT WHERE email = req.email) → 409 `{"code": "EMAIL_EXISTS", "message": "An account with this email already exists."}`
     - Hash password, create User, commit
     - Generate access + refresh tokens
     - Return `{"success": true, "data": TokenResponse}`

   - `POST /login`:
     - Find user by email → 401 `{"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}` if not found
     - Verify password → same 401 if wrong
     - Generate tokens
     - Return `{"success": true, "data": TokenResponse}`

   - `POST /refresh`:
     - Decode refresh token via auth_service.decode_token()
     - Query user by decoded user_id → 401 if user doesn't exist
     - Generate new access token only
     - Return `{"success": true, "data": AccessTokenResponse}`

   - `GET /me`:
     - Depends on `get_current_user` from deps
     - Return `{"success": true, "data": UserResponse}`

2. MODIFY `backend/app/deps.py`:
   ```python
   from fastapi import Depends, HTTPException
   from fastapi.security import OAuth2PasswordBearer
   from sqlalchemy import select
   from sqlalchemy.ext.asyncio import AsyncSession

   from app.database import get_db
   from app.models.user import User
   from app.services import auth_service

   oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


   async def get_current_user(
       token: str = Depends(oauth2_scheme),
       db: AsyncSession = Depends(get_db),
   ) -> User:
       user_id = auth_service.decode_token(token)
       result = await db.execute(select(User).where(User.id == user_id))
       user = result.scalar_one_or_none()
       if not user:
           raise HTTPException(
               status_code=401,
               detail={"error": {"code": "INVALID_TOKEN", "message": "User not found."}},
           )
       return user
   ```

3. MODIFY `backend/app/main.py` — add after the health endpoint:
   ```python
   from app.routers import auth
   app.include_router(auth.router)
   ```

CODING STYLE:
- All route handlers are `async def`
- Every response wrapped in `{"success": true/false, "data"/"error": ...}`
- Error responses use HTTPException with `detail={"error": {"code": "...", "message": "..."}}`
- Use `select()` from sqlalchemy for queries, not session.query()
- DB operations: `await db.execute(...)`, `await db.commit()`, `await db.refresh(obj)`

CONSTRAINTS:
- Do NOT modify the User model or schemas
- Error responses must never reveal whether an email exists (login returns same error for wrong email and wrong password)
- The OAuth2PasswordBearer tokenUrl is just for Swagger docs — actual auth uses Bearer token in Authorization header
```

## Prompt 1.4 — Frontend Auth Pages

```
ROLE: You are implementing the frontend authentication pages for ZeroPath Security Scanner.

CONTEXT:
The frontend exists with:
- `frontend/lib/api.ts` — `apiFetch<T>(endpoint, options)` returning `ApiResponse<T>` with `{success, data?, error?}`. Auto-injects Authorization header from localStorage. Clears tokens on 401.
- `frontend/lib/auth.ts` — `getAccessToken()`, `getRefreshToken()`, `setTokens(access, refresh)`, `clearTokens()`. All use localStorage.
- `frontend/app/layout.tsx` — Root layout with Inter font, Tailwind globals
- `frontend/app/page.tsx` — Placeholder page

Backend auth API:
- `POST /api/auth/signup` body: `{email, password}` → `{success: true, data: {access_token, refresh_token, token_type}}`
- `POST /api/auth/login` body: `{email, password}` → same response shape
- Errors: `{success: false, error: {code, message}}`

TASK:
Create login and signup pages, and update the root page to redirect based on auth state.

CREATE:

1. `frontend/app/login/page.tsx`:
   - `"use client"` directive at top
   - Interface: `LoginForm { email: string; password: string }`
   - State: `form` (LoginForm, default empty strings), `error` (string, default ""), `loading` (boolean, default false)
   - Import `useRouter` from `next/navigation`, `useState` from react
   - Import `apiFetch` from `@/lib/api`, `setTokens` from `@/lib/auth`
   - Form with email input (type="email") and password input (type="password")
   - On submit (prevent default):
     1. Set loading=true, clear error
     2. Call `apiFetch<{access_token: string; refresh_token: string}>("/api/auth/login", {method: "POST", body: JSON.stringify(form)})`
     3. On success: `setTokens(data.access_token, data.refresh_token)`, `router.push("/dashboard")`
     4. On error: `setError(res.error?.message || "Login failed.")`
     5. Set loading=false in finally
   - Error displayed below form in red text: `{error && <p className="text-red-600 text-sm mt-2">{error}</p>}`
   - Submit button: disabled when loading, shows "Signing in..." when loading, "Sign in" otherwise
   - Link at bottom: `Don't have an account?` → `/signup`
   - Layout: centered card with white background, shadow, rounded corners, max-w-md, padding
   - Page background: `bg-gray-50 min-h-screen flex items-center justify-center`
   - Heading: "Sign in to ZeroPath"

2. `frontend/app/signup/page.tsx`:
   - Same structure as login, but with:
   - Interface: `SignupForm { email: string; password: string; confirmPassword: string }`
   - Additional confirm password field
   - Client-side validation: if `password !== confirmPassword`, set error "Passwords do not match." and return before API call
   - Client-side validation: if `password.length < 8`, set error "Password must be at least 8 characters."
   - Calls `POST /api/auth/signup`
   - On success: setTokens, redirect to `/dashboard`
   - Link at bottom: `Already have an account?` → `/login`
   - Heading: "Create your account"

3. MODIFY `frontend/app/page.tsx`:
   ```tsx
   "use client";

   import { useEffect } from "react";
   import { useRouter } from "next/navigation";
   import { getAccessToken } from "@/lib/auth";

   export default function Home() {
     const router = useRouter();

     useEffect(() => {
       if (getAccessToken()) {
         router.replace("/dashboard");
       } else {
         router.replace("/login");
       }
     }, [router]);

     return (
       <div className="min-h-screen flex items-center justify-center">
         <div className="animate-pulse text-gray-400">Loading...</div>
       </div>
     );
   }
   ```

CODING STYLE:
- `"use client"` directive on every page with interactivity
- Interfaces at top of file, below imports
- Input styling: `border border-gray-300 rounded-lg px-3 py-2 w-full focus:outline-none focus:ring-2 focus:ring-blue-500`
- Button styling: `bg-blue-600 text-white rounded-lg px-4 py-2 w-full hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed`
- Label styling: `text-sm font-medium text-gray-700`
- Card styling: `bg-white rounded-xl shadow-md p-8 w-full max-w-md`
- No `any` types anywhere

CONSTRAINTS:
- Do NOT create the dashboard page yet — that's Phase 2
- Do NOT create NavHeader — that's Phase 2
- Redirect to /dashboard on success even though the page doesn't exist yet (it will 404 until Phase 2)
```

---

**Verification after Phase 1:**
1. `POST /api/auth/signup` with `{"email": "test@example.com", "password": "password123"}` → 200 with tokens
2. Same email again → 409 `EMAIL_EXISTS`
3. `POST /api/auth/login` with correct creds → 200 with tokens
4. Wrong password → 401 `INVALID_CREDENTIALS`
5. `GET /api/auth/me` with Bearer token → 200 with user data
6. Without token → 401
7. Frontend login form works end-to-end
8. Frontend signup form validates passwords match and minimum length
