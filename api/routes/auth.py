"""Authentication routes: register, login, refresh, logout."""

import os
import logging
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from suno.common.models import User, Tier, Membership
from suno.common.enums import TierName, MembershipLifecycle, AccountStatus
from suno.provisioning.account_ops import AccountProvisioner
from services.auth import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/register", response_model=TokenResponse)
@limiter.limit("10/minute")
async def register(
    request: Request,
    body: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime
    from suno.common.models import Account
    import uuid as uuid_lib

    # Beta whitelist: only these emails can register
    BETA_WHITELIST = {
        "sunoclips@elegantsolarinc.com",
        "nicole@elegantsolarinc.com",
        "elliott@elegantsolarinc.com",
    }

    if body.email.lower() not in BETA_WHITELIST:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not on beta access list. Contact support for early access."
        )

    # Check if user already exists
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    try:
        # 1. Create user WITH password_hash
        user = User(
            email=body.email,
            password_hash=hash_password(body.password),
        )
        db.add(user)
        await db.flush()
        logger.info(f"Created user {user.id} for email {body.email}")

        # 2. Get or create "starter" tier
        # Use string literal to avoid SQLEnum type coercion (column is VARCHAR, not enum)
        tier_result = await db.execute(select(Tier).where(Tier.name == "starter"))
        tier = tier_result.scalar_one_or_none()
        if not tier:
            tier = Tier(
                name="starter",
                max_daily_clips=10,
                max_platforms=3,
                platforms=["tiktok", "instagram", "youtube"],
                auto_posting=False,
                scheduling=False,
                analytics=False,
                api_access=False,
            )
            db.add(tier)
            await db.flush()
            logger.info("Created starter tier")

        # 3. Create membership
        membership = Membership(
            user_id=user.id,
            tier_id=tier.id,
            whop_membership_id=f"beta_{user.id}",
            status=MembershipLifecycle.ACTIVE,
            activated_at=datetime.utcnow(),
        )
        db.add(membership)
        await db.flush()
        logger.info(f"Created membership {membership.id} for user {user.id}")

        # 4. Create account (in same transaction)
        account = Account(
            membership_id=membership.id,
            workspace_id=f"ws_{uuid_lib.uuid4().hex[:12]}",
            status=AccountStatus.ACTIVE,
            automation_enabled=True,
        )
        db.add(account)
        await db.flush()
        logger.info(f"Created account {account.workspace_id} for membership {membership.id}")

        # 5. Commit ONCE at the end (atomic transaction)
        await db.commit()
        logger.info(f"Registration complete for {body.email}")

        # Create tokens
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            samesite="lax",
            secure=os.getenv("APP_ENV") == "production",
            max_age=7 * 24 * 3600,
            path="/api/auth",
        )
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            samesite="lax",
            secure=os.getenv("APP_ENV") == "production",
            max_age=15 * 60,
            path="/",
        )

        return TokenResponse(access_token=access_token)

    except Exception as e:
        await db.rollback()
        logger.error(f"Registration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed. Please try again."
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Check if user has an active membership
    membership_result = await db.execute(
        select(Membership).where(Membership.user_id == user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None or membership.status != MembershipLifecycle.ACTIVE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not activated")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("APP_ENV") == "production",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("APP_ENV") == "production",
        max_age=15 * 60,
        path="/",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    payload = decode_refresh_token(refresh_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id_str = payload.get("sub")
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    new_access_token = create_access_token({"sub": str(user.id)})
    new_refresh_token = create_refresh_token({"sub": str(user.id)})

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("APP_ENV") == "production",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        samesite="lax",
        secure=os.getenv("APP_ENV") == "production",
        max_age=15 * 60,
        path="/",
    )

    return TokenResponse(access_token=new_access_token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("refresh_token", path="/api/auth")
    response.delete_cookie("access_token", path="/")
    return {"detail": "Logged out"}
