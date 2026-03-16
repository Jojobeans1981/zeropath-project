# Phase 10 (Stretch): RBAC + CI/CD Webhooks — Implementation Prompts

## Prompt 10.1 — User Roles + Role Dependency

```
ROLE: You are implementing role-based access control for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/user.py` — User model (id, email, password_hash, created_at, updated_at)
- `backend/app/deps.py` — get_current_user() dependency
- `backend/app/routers/auth.py` — signup, login, refresh, me
- `backend/app/routers/repos.py` — repo CRUD (all require get_current_user)
- `backend/app/routers/scans.py` — scan create/get/compare (all require get_current_user)
- `backend/app/routers/findings.py` — finding get/triage (all require get_current_user)

Roles: admin (all access), member (own data + create), viewer (own data read-only)

TASK:

1. ADD to `backend/app/models/user.py`:
   ```python
   role = Column(String, default="member", nullable=False)
   ```

2. Run migration: `alembic revision --autogenerate -m "add_role_to_users"` then `alembic upgrade head`

3. MODIFY `backend/app/deps.py` — add role requirement factory:
   ```python
   def require_role(allowed_roles: list[str]):
       """Dependency factory: ensures current user has one of the allowed roles."""
       async def role_checker(
           current_user: User = Depends(get_current_user),
       ) -> User:
           if current_user.role not in allowed_roles:
               raise HTTPException(
                   status_code=403,
                   detail={"error": {"code": "INSUFFICIENT_ROLE", "message": f"This action requires one of these roles: {', '.join(allowed_roles)}"}},
               )
           return current_user
       return role_checker
   ```

4. MODIFY existing routers to use role requirements:

   `repos.py`:
   - POST /: change dependency to `Depends(require_role(["admin", "member"]))`
   - GET / and GET /{repo_id}: keep get_current_user (all roles can read their own)

   `scans.py`:
   - POST /: `Depends(require_role(["admin", "member"]))`
   - GET endpoints: keep get_current_user

   `findings.py`:
   - PATCH /{finding_id}/triage: `Depends(require_role(["admin", "member"]))`
   - GET: keep get_current_user

5. MODIFY `backend/app/schemas/auth.py`:
   - Add `role: str` to UserResponse

6. MODIFY `backend/app/routers/auth.py`:
   - The first user to sign up gets role "admin"
   - Subsequent users get "member"
   - Check: `SELECT COUNT(*) FROM users` — if 0, assign "admin"

CODING STYLE:
- Role check via dependency injection, not inline if-statements
- First user = admin is a simple bootstrap mechanism

CONSTRAINTS:
- Viewers can read their own repos/scans/findings but cannot create or triage
- Admins see all data (modify queries in services if admin — or leave for now and just do role gating on writes)
- Do NOT add admin endpoints yet — that's the next prompt
```

## Prompt 10.2 — Admin Endpoints + Frontend

```
ROLE: You are implementing admin user management for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- User model now has `role` field (admin/member/viewer)
- `deps.py` has `require_role()` factory
- Existing routers have role-gated write operations

TASK:

1. CREATE `backend/app/routers/admin.py`:
   ```python
   from fastapi import APIRouter, Depends, HTTPException
   from sqlalchemy import select, func
   from sqlalchemy.ext.asyncio import AsyncSession
   from app.deps import get_db, require_role
   from app.models.user import User

   router = APIRouter(prefix="/api/admin", tags=["admin"])


   @router.get("/users")
   async def list_users(
       current_user: User = Depends(require_role(["admin"])),
       db: AsyncSession = Depends(get_db),
   ):
       result = await db.execute(select(User).order_by(User.created_at.desc()))
       users = result.scalars().all()
       return {
           "success": True,
           "data": [
               {"id": u.id, "email": u.email, "role": u.role, "created_at": u.created_at.isoformat()}
               for u in users
           ],
       }


   @router.patch("/users/{user_id}")
   async def update_user_role(
       user_id: str,
       body: dict,
       current_user: User = Depends(require_role(["admin"])),
       db: AsyncSession = Depends(get_db),
   ):
       new_role = body.get("role")
       if new_role not in {"admin", "member", "viewer"}:
           raise HTTPException(status_code=422, detail={"error": {"code": "INVALID_ROLE", "message": "Role must be admin, member, or viewer."}})

       if user_id == current_user.id:
           raise HTTPException(status_code=400, detail={"error": {"code": "SELF_MODIFY", "message": "Cannot change your own role."}})

       # Prevent demoting last admin
       if new_role != "admin":
           admin_count = await db.execute(select(func.count(User.id)).where(User.role == "admin"))
           count = admin_count.scalar()
           target = await db.execute(select(User).where(User.id == user_id))
           target_user = target.scalar_one_or_none()
           if target_user and target_user.role == "admin" and count <= 1:
               raise HTTPException(status_code=400, detail={"error": {"code": "LAST_ADMIN", "message": "Cannot demote the last admin."}})

       result = await db.execute(select(User).where(User.id == user_id))
       user = result.scalar_one_or_none()
       if not user:
           raise HTTPException(status_code=404, detail={"error": {"code": "NOT_FOUND", "message": "User not found."}})

       user.role = new_role
       await db.commit()

       return {"success": True, "data": {"id": user.id, "email": user.email, "role": user.role}}
   ```

2. MODIFY `backend/app/main.py` — add:
   ```python
   from app.routers import admin
   app.include_router(admin.router)
   ```

3. CREATE `frontend/app/admin/page.tsx`:
   - `"use client"`, auth guard
   - Fetch `GET /api/auth/me` to check role — if not admin, redirect to /dashboard
   - Fetch `GET /api/admin/users` on mount
   - Table: columns for email, role (dropdown select), created date
   - Role dropdown: on change, call PATCH /api/admin/users/:id with {role: newValue}
   - Disable dropdown for current user's row
   - Show success/error inline

4. MODIFY `frontend/app/components/NavHeader.tsx`:
   - After fetching user data, check role
   - If role === "admin", show "Admin" link → `/admin` in the nav bar

CODING STYLE:
- Admin-only endpoints via require_role(["admin"])
- Safety checks: can't modify own role, can't demote last admin

CONSTRAINTS:
- Admin page is simple table — not a full user management system
- Role changes take effect on next API call (no token invalidation)
```

## Prompt 10.3 — GitHub Webhook Endpoint

```
ROLE: You are implementing GitHub webhook scanning for ZeroPath Security Scanner.

CONTEXT:
The backend has:
- `backend/app/models/repository.py` — Repository (url, name)
- `backend/app/models/scan.py` — Scan
- `backend/app/workers/scan_worker.py` — run_scan task
- `backend/app/config.py` — Settings class

TASK:

1. ADD to `backend/app/config.py`:
   ```python
   github_webhook_secret: str = ""
   ```

2. ADD to `.env.example`:
   ```
   GITHUB_WEBHOOK_SECRET=your-webhook-secret
   ```

3. CREATE `backend/app/services/webhook_service.py`:
   ```python
   import hashlib
   import hmac
   import logging

   logger = logging.getLogger(__name__)


   def verify_github_signature(body: bytes, signature: str, secret: str) -> bool:
       if not signature.startswith("sha256="):
           return False
       expected = "sha256=" + hmac.new(
           secret.encode(),
           body,
           hashlib.sha256,
       ).hexdigest()
       return hmac.compare_digest(expected, signature)
   ```

4. CREATE `backend/app/routers/webhooks.py`:
   ```python
   import logging
   from fastapi import APIRouter, Request, HTTPException
   from sqlalchemy import select
   from app.config import settings
   from app.database import async_session_maker
   from app.models.repository import Repository
   from app.models.scan import Scan
   from app.services.webhook_service import verify_github_signature

   logger = logging.getLogger(__name__)
   router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


   @router.post("/github")
   async def github_webhook(request: Request):
       if not settings.github_webhook_secret:
           raise HTTPException(status_code=501, detail="Webhooks not configured")

       # Verify signature
       body = await request.body()
       signature = request.headers.get("X-Hub-Signature-256", "")
       if not verify_github_signature(body, signature, settings.github_webhook_secret):
           raise HTTPException(status_code=403, detail="Invalid signature")

       # Parse event
       event_type = request.headers.get("X-GitHub-Event", "")
       if event_type != "push":
           return {"status": "ignored", "reason": f"Event type '{event_type}' not handled"}

       payload = await request.json()
       clone_url = payload.get("repository", {}).get("clone_url", "")
       # Normalize: strip .git suffix
       repo_url = clone_url.rstrip(".git").rstrip("/")

       # Find matching repo
       async with async_session_maker() as db:
           result = await db.execute(
               select(Repository).where(Repository.url == repo_url)
           )
           repo = result.scalar_one_or_none()

           if not repo:
               logger.info("[Webhook] No tracked repo matches %s", repo_url)
               return {"status": "ignored", "reason": "Repository not tracked"}

           # Create scan
           scan = Scan(repo_id=repo.id, status="queued")
           db.add(scan)
           await db.commit()
           await db.refresh(scan)

           # Enqueue task
           from app.workers.scan_worker import run_scan
           run_scan.delay(scan.id)

           logger.info("[Webhook] Triggered scan %s for repo %s", scan.id, repo.name)
           return {"status": "ok", "scan_id": scan.id}
   ```

5. MODIFY `backend/app/main.py` — add:
   ```python
   from app.routers import webhooks
   app.include_router(webhooks.router)
   ```

CODING STYLE:
- `[Webhook]` log prefix
- HMAC signature verification before any processing
- Always return 200 (GitHub retries on non-2xx)
- Normalize repo URLs before matching

CONSTRAINTS:
- No JWT auth — uses webhook signature verification
- Only handles "push" events
- Untracked repos return 200 with "ignored" status
- GITHUB_WEBHOOK_SECRET must be set for webhooks to work
```

---

**Verification after Phase 10:**
1. Viewers cannot create scans or triage findings (403)
2. Members can create and triage but not access admin
3. Admins can list/modify user roles
4. First signup gets admin role
5. Cannot demote last admin
6. GitHub webhook with valid signature triggers scan
7. Invalid signature returns 403
