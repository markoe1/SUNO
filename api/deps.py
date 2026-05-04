"""FastAPI dependency injection: database session, current user."""

import uuid
from typing import AsyncGenerator, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import AsyncSessionLocal
from suno.common.models import User, Membership
from suno.common.enums import MembershipLifecycle
from services.auth import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    token: Optional[str] = None

    # 1. Try Authorization: Bearer <token> header
    if credentials and credentials.credentials:
        token = credentials.credentials

    # 2. Fallback: access_token cookie (set by web login form)
    if not token:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str: Optional[str] = payload.get("sub")
    if user_id_str is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Check if user has an active membership
    membership_result = await db.execute(
        select(Membership).where(Membership.user_id == user.id)
    )
    membership = membership_result.scalar_one_or_none()
    if membership is None or membership.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User membership not active")

    return user


async def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    try:
        return await get_current_user(request=request, credentials=credentials, db=db)
    except HTTPException:
        return None
