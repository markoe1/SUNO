"""Editor portal auth and data routes.

Editors are team members assigned clips by an operator. They authenticate
with email + password (set when the operator creates or updates them) and
receive an editor_access_token JWT cookie — completely separate from the
operator access_token.

Routes:
  POST /api/editor/login       — email+password → sets editor_access_token cookie
  POST /api/editor/logout      — clears editor_access_token cookie
  GET  /api/editor/me          — returns editor profile
  GET  /api/editor/clips       — returns clips assigned to this editor
  PATCH /api/editor/clips/{id}/status — editor advances clip status
"""

import os
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_editor, get_db
from db.models_v2 import Client, ClientClip, ClipStatus, Editor
from services.auth import create_editor_access_token, hash_password, verify_password
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/editor", tags=["editor-portal"])

APP_ENV = os.getenv("APP_ENV", "development")


# ---------------------------------------------------------------------------
# Request / response schemas
# ---------------------------------------------------------------------------

class EditorLoginRequest(BaseModel):
    email: str
    password: str


class EditorMeResponse(BaseModel):
    id: UUID
    name: str
    email: Optional[str]
    rate_per_clip: float
    total_clips_edited: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EditorSetPasswordRequest(BaseModel):
    password: str


class EditorClipStatusUpdate(BaseModel):
    status: str


class EditorClipResponse(BaseModel):
    id: UUID
    client_id: UUID
    client_name: Optional[str] = None
    title: Optional[str]
    status: str
    hook_used: Optional[str]
    content_notes: Optional[str]
    drive_folder: Optional[str]
    raw_file_path: Optional[str]
    tiktok_url: Optional[str]
    total_views: int
    posted_at: Optional[str]
    created_at: str

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else str(v)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@router.post("/login")
async def editor_login(
    data: EditorLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Editor email + password login. Sets editor_access_token httponly cookie."""
    result = await db.execute(
        select(Editor).where(Editor.email == data.email).where(Editor.is_active == True)  # noqa: E712
    )
    editor = result.scalar_one_or_none()

    if not editor or not editor.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(data.password, editor.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_editor_access_token(str(editor.id))
    response.set_cookie(
        key="editor_access_token",
        value=token,
        httponly=True,
        secure=APP_ENV == "production",
        samesite="lax",
        max_age=72 * 3600,
        path="/",
    )
    logger.info("Editor login: %s (id=%s)", editor.email, editor.id)
    return {"ok": True, "editor_id": str(editor.id), "name": editor.name}


@router.post("/logout")
async def editor_logout(response: Response):
    """Clear the editor portal session cookie."""
    response.delete_cookie("editor_access_token", path="/")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Editor data endpoints (require editor_access_token cookie)
# ---------------------------------------------------------------------------

@router.get("/me", response_model=EditorMeResponse)
async def editor_me(
    current_editor: Editor = Depends(get_current_editor),
):
    return EditorMeResponse.model_validate(current_editor)


@router.get("/clips", response_model=List[EditorClipResponse])
async def editor_clips(
    clip_status: Optional[str] = None,
    current_editor: Editor = Depends(get_current_editor),
    db: AsyncSession = Depends(get_db),
):
    """Return clips assigned to this editor, with optional status filter."""
    query = (
        select(ClientClip, Client.name.label("client_name"))
        .join(Client, ClientClip.client_id == Client.id)
        .where(ClientClip.editor_id == current_editor.id)
    )
    if clip_status:
        try:
            query = query.where(ClientClip.status == ClipStatus(clip_status.upper()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {clip_status}")

    query = query.order_by(ClientClip.created_at.desc())
    result = await db.execute(query)
    rows = result.all()

    clips = []
    for clip, client_name in rows:
        d = EditorClipResponse.model_validate(clip)
        d.client_name = client_name
        clips.append(d)
    return clips


@router.patch("/clips/{clip_id}/status", response_model=EditorClipResponse)
async def editor_update_clip_status(
    clip_id: UUID,
    data: EditorClipStatusUpdate,
    current_editor: Editor = Depends(get_current_editor),
    db: AsyncSession = Depends(get_db),
):
    """Editor advances a clip to EDITING or REVIEW. Cannot approve or post."""
    _EDITOR_ALLOWED_TRANSITIONS = {
        ClipStatus.RAW: ClipStatus.EDITING,
        ClipStatus.EDITING: ClipStatus.REVIEW,
    }
    _EDITOR_ALLOWED_TARGET = {ClipStatus.EDITING, ClipStatus.REVIEW}

    try:
        new_status = ClipStatus(data.status.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {data.status}")

    if new_status not in _EDITOR_ALLOWED_TARGET:
        raise HTTPException(
            status_code=403,
            detail=f"Editors can only set status to EDITING or REVIEW",
        )

    result = await db.execute(
        select(ClientClip)
        .where(ClientClip.id == clip_id)
        .where(ClientClip.editor_id == current_editor.id)
    )
    clip = result.scalar_one_or_none()
    if not clip:
        raise HTTPException(status_code=404, detail="Clip not found or not assigned to you")

    allowed_next = _EDITOR_ALLOWED_TRANSITIONS.get(clip.status)
    if allowed_next != new_status:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {clip.status.value} to {new_status.value}",
        )

    clip.status = new_status
    await db.commit()
    await db.refresh(clip)

    # Fetch client name for response
    client_result = await db.execute(select(Client.name).where(Client.id == clip.client_id))
    client_name = client_result.scalar_one_or_none()

    resp = EditorClipResponse.model_validate(clip)
    resp.client_name = client_name
    logger.info("Editor %s moved clip %s → %s", current_editor.name, clip_id, new_status.value)
    return resp
