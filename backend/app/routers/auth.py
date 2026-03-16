from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas.auth import (
    SignupRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    AccessTokenResponse,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/signup")
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    if len(req.password) < 8:
        raise HTTPException(
            status_code=422,
            detail={"error": {"code": "VALIDATION_ERROR", "message": "Password must be at least 8 characters."}},
        )

    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error": {"code": "EMAIL_EXISTS", "message": "An account with this email already exists."}},
        )

    user = User(
        email=req.email,
        password_hash=auth_service.hash_password(req.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    tokens = TokenResponse(
        access_token=auth_service.create_access_token(user.id),
        refresh_token=auth_service.create_refresh_token(user.id),
    )
    return {"success": True, "data": tokens.model_dump()}


@router.post("/login")
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()

    if not user or not auth_service.verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_CREDENTIALS", "message": "Invalid email or password."}},
        )

    tokens = TokenResponse(
        access_token=auth_service.create_access_token(user.id),
        refresh_token=auth_service.create_refresh_token(user.id),
    )
    return {"success": True, "data": tokens.model_dump()}


@router.post("/refresh")
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    user_id = auth_service.decode_token(req.refresh_token)

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "INVALID_TOKEN", "message": "User not found."}},
        )

    token = AccessTokenResponse(
        access_token=auth_service.create_access_token(user.id),
    )
    return {"success": True, "data": token.model_dump()}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    user_data = UserResponse(
        id=current_user.id,
        email=current_user.email,
        created_at=current_user.created_at,
    )
    return {"success": True, "data": user_data.model_dump()}
