from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.deps import require_role
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
