"""Settings routes: Whop session management, job pause/resume."""

import json
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models import User, UserSecret
from services.secrets import decrypt_blob, encrypt_blob
from services.whop_client import WhopAuthError, WhopClient

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    has_whop_session: bool
    jobs_paused: bool


class WhopSessionRequest(BaseModel):
    cookies_json: str  # Raw cookie string or JSON from DevTools


class WhopSessionResponse(BaseModel):
    valid: bool
    error: Optional[str] = None


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSecret).where(UserSecret.user_id == current_user.id)
    )
    secret = result.scalar_one_or_none()
    return SettingsResponse(
        has_whop_session=secret is not None,
        jobs_paused=current_user.jobs_paused,
    )


@router.post("/whop-session", response_model=WhopSessionResponse)
async def import_whop_session(
    body: WhopSessionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Parse the cookie input — accept either:
    # 1. JSON object: {"cookie_name": "value", ...}
    # 2. Cookie string: "name=value; name2=value2"
    cookies_dict: dict
    raw = body.cookies_json.strip()

    if raw.startswith("{"):
        try:
            cookies_dict = json.loads(raw)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON cookie format",
            )
    else:
        # Parse cookie string format: "name=value; name2=value2"
        cookies_dict = {}
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies_dict[k.strip()] = v.strip()

    if not cookies_dict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No cookies parsed from input",
        )

    # Validate session by hitting Whop
    try:
        client = WhopClient(cookies=cookies_dict)
        valid = client.validate_session()
    except WhopAuthError:
        valid = False
    except Exception as exc:
        return WhopSessionResponse(valid=False, error=str(exc))

    if not valid:
        return WhopSessionResponse(
            valid=False,
            error="Session validation failed — cookies may be expired. Please re-export from your browser.",
        )

    # Encrypt and store
    encrypted = encrypt_blob({"cookies": cookies_dict})

    result = await db.execute(
        select(UserSecret).where(UserSecret.user_id == current_user.id)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.encrypted_blob = encrypted
    else:
        db.add(
            UserSecret(
                id=uuid.uuid4(),
                user_id=current_user.id,
                encrypted_blob=encrypted,
            )
        )

    await db.commit()
    return WhopSessionResponse(valid=True)


@router.delete("/whop-session")
async def delete_whop_session(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSecret).where(UserSecret.user_id == current_user.id)
    )
    secret = result.scalar_one_or_none()
    if secret:
        await db.delete(secret)
        await db.commit()
    return {"detail": "Whop session cleared"}


@router.post("/pause-jobs")
async def pause_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.jobs_paused = True
    await db.commit()
    return {"detail": "Jobs paused", "jobs_paused": True}


@router.post("/resume-jobs")
async def resume_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    current_user.jobs_paused = False
    await db.commit()
    return {"detail": "Jobs resumed", "jobs_paused": False}
