"""FastAPI dependency injection: database session, current user, current client."""

import uuid
from typing import AsyncGenerator, Optional

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.engine import AsyncSessionLocal
from db.models import User
from services.auth import decode_access_token, decode_client_access_token, decode_editor_access_token

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
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

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


async def get_current_client(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Validate the client_access_token cookie and return the Client object.

    Used by client portal routes — completely separate from operator auth.
    """
    from db.models_v2 import Client

    token = request.cookies.get("client_access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client portal token required",
        )

    payload = decode_client_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired portal token",
        )

    client_id_str: Optional[str] = payload.get("sub")
    if not client_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        client_id = uuid.UUID(client_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found")

    return client


async def get_current_editor(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Validate the editor_access_token cookie and return the Editor object."""
    from db.models_v2 import Editor

    token = request.cookies.get("editor_access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Editor portal token required",
        )

    payload = decode_editor_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired editor token",
        )

    editor_id_str: Optional[str] = payload.get("sub")
    if not editor_id_str:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    try:
        editor_id = uuid.UUID(editor_id_str)
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    result = await db.execute(select(Editor).where(Editor.id == editor_id))
    editor = result.scalar_one_or_none()
    if editor is None or not editor.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Editor not found or inactive")

    return editor
