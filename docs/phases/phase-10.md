# Phase 10 (Stretch): RBAC + CI/CD Webhooks

## Objective
Add role-based access control (admin, member, viewer) and GitHub webhook integration for automated scanning on push events.

## Current State (After Phase 9)
- **Backend:** Complete API with auth, repos (private support), scans (SARIF, WebSocket), findings, triage, comparison. All features from Phases 0-9.
- **Frontend:** Complete dashboard with real-time WebSocket updates.
- **Database:** 5 tables. User model has no role field (all users equal).
- **Auth:** JWT-based, all authenticated users have identical permissions.

## Architecture Context

### Schema Changes
Extend User model:
```
User (extend)
├── ...existing fields...
└── role: String (default "member", enum: "admin", "member", "viewer")
```

### Role Permissions
| Action | Admin | Member | Viewer |
|--------|-------|--------|--------|
| View own repos/scans/findings | Yes | Yes | Yes |
| View ALL repos/scans/findings | Yes | No | No |
| Create repos / trigger scans | Yes | Yes | No |
| Triage findings | Yes | Yes | No |
| Manage users (list, change roles) | Yes | No | No |
| Receive webhooks | Yes | Yes | — |

### New API Endpoints
| Method | Path | Auth | Role | Request | Response |
|--------|------|------|------|---------|----------|
| GET | `/api/admin/users` | Yes | Admin | — | Array of users with roles |
| PATCH | `/api/admin/users/:id` | Yes | Admin | `{ role: string }` | Updated user |
| POST | `/api/webhooks/github` | No (signature-verified) | — | GitHub push event payload | 200 OK |

### Webhook Flow
```
GitHub push event → POST /api/webhooks/github
  1. Verify X-Hub-Signature-256 header using GITHUB_WEBHOOK_SECRET
  2. Parse payload: extract repo URL, branch, commit SHA
  3. Find matching Repository in DB (by URL)
  4. If found and push is to default branch: create Scan, enqueue task
  5. Return 200 OK
```

## Coding Standards
- Python: snake_case, async handlers, `[RBAC]` prefix for access control logs, `[Webhook]` for webhook processing
- Role checking via dependency injection, not inline checks

## Deliverables

1. **Alembic migration** — add `role` column to users (default "member")
2. **`backend/app/deps.py`** (extend) — add `require_role()` dependency
3. **`backend/app/routers/admin.py`** — admin user management endpoints
4. **`backend/app/routers/webhooks.py`** — GitHub webhook endpoint
5. **`backend/app/services/webhook_service.py`** — signature verification + scan trigger
6. **All existing routers** (modify) — add role requirements
7. **`frontend/app/admin/page.tsx`** — admin user management page
8. **`frontend/app/components/NavHeader.tsx`** (extend) — admin link for admin users

## Technical Specification

### backend/app/deps.py (extend)

```python
def require_role(allowed_roles: list[str]):
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail={"code": "INSUFFICIENT_ROLE", "message": f"Requires role: {', '.join(allowed_roles)}"}
            )
        return current_user
    return role_checker
```

Usage: `current_user: User = Depends(require_role(["admin", "member"]))`

### Existing Router Modifications
- **repos.py**: POST requires `["admin", "member"]`. GET endpoints: members see own repos, admins see all.
- **scans.py**: POST create requires `["admin", "member"]`. GET endpoints: members see own, admins see all.
- **findings.py**: PATCH triage requires `["admin", "member"]`. GET: members see own, admins see all.

### backend/app/routers/admin.py
- Router prefix: `/api/admin`
- All endpoints require `Depends(require_role(["admin"]))`
- `GET /users`: list all users with id, email, role, created_at
- `PATCH /users/{user_id}`: update role. Body: `{ role: "admin" | "member" | "viewer" }`. Cannot change own role. Cannot demote the last admin.

### backend/app/routers/webhooks.py
- Router prefix: `/api/webhooks`
- `POST /github`:
  - No JWT auth — uses webhook signature verification instead
  - Read raw body bytes for signature verification
  - Verify `X-Hub-Signature-256` header:
    ```python
    import hmac, hashlib
    expected = "sha256=" + hmac.new(
        settings.github_webhook_secret.encode(),
        body_bytes,
        hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(403)
    ```
  - Parse JSON body. Check `action` or event type from `X-GitHub-Event` header.
  - If event is `push`: extract `repository.clone_url` and `ref` (branch)
  - Find Repository in DB matching `clone_url` (strip `.git` suffix for comparison)
  - If found: create Scan, enqueue Celery task
  - If not found: return 200 OK (acknowledge but don't process — repo not tracked)
  - Always return 200 (GitHub retries on non-2xx)

### backend/app/services/webhook_service.py
- `verify_github_signature(body: bytes, signature: str, secret: str) -> bool`
- `process_push_event(db, payload: dict) -> Scan | None`: find repo, create scan if matched

### frontend/app/admin/page.tsx
- `"use client"`, auth guard, role guard (redirect non-admins to `/dashboard`)
- Fetch `GET /api/admin/users` on mount
- Table: email, role (dropdown to change), created_at
- Role dropdown: on change, call `PATCH /api/admin/users/:id` with new role
- Cannot change own role (dropdown disabled for current user)
- Success toast or inline confirmation on role change

### frontend/app/components/NavHeader.tsx (extend)
- If user role is `admin`, show "Admin" link → `/admin` in nav

## Acceptance Criteria

1. Viewers can browse repos/scans/findings but cannot create scans or triage
2. Members can do everything except access admin endpoints
3. Admins can list and modify user roles
4. Cannot demote the last admin
5. GitHub webhook with valid signature creates scan for matching repo
6. GitHub webhook with invalid signature returns 403
7. Webhook for untracked repo returns 200 (no-op)
8. Admin page lists users and allows role changes
9. NavHeader shows "Admin" link for admin users only
10. `GITHUB_WEBHOOK_SECRET` env var is required for webhook functionality
