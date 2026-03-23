"""Editor management routes — manage your clip editing team."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import Editor, ClientClip, ClipStatus
from services.auth import hash_password
from services.email import send_editor_welcome_email
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/editors", tags=["editors"])


class EditorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    rate_per_clip: float = Field(10.0, ge=0)
    password: Optional[str] = Field(None, min_length=8, description="Portal login password for this editor")


class EditorSetPassword(BaseModel):
    password: str = Field(..., min_length=8)


class EditorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    rate_per_clip: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None


class EditorResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    email: Optional[str]
    rate_per_clip: float
    total_clips_edited: int
    avg_turnaround_hours: Optional[float]
    quality_score: Optional[float]
    is_active: bool
    # computed
    clips_in_progress: int = 0
    clips_pending: int = 0

    model_config = ConfigDict(from_attributes=True)


@router.post("", response_model=EditorResponse, status_code=status.HTTP_201_CREATED)
async def create_editor(
    data: EditorCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    editor = Editor(
        user_id=current_user.id,
        name=data.name,
        email=data.email,
        rate_per_clip=data.rate_per_clip,
        password_hash=hash_password(data.password) if data.password else None,
    )
    db.add(editor)
    await db.commit()
    await db.refresh(editor)
    logger.info(f"Created editor {editor.name}")

    # Send welcome email with portal login instructions if email + password provided
    if data.email and data.password:
        send_editor_welcome_email(
            editor_email=data.email,
            editor_name=data.name,
            password=data.password,
        )

    return EditorResponse(**editor.__dict__, clips_in_progress=0, clips_pending=0)


@router.get("", response_model=List[EditorResponse])
async def list_editors(
    active_only: bool = True,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Editor).where(Editor.user_id == current_user.id)
    if active_only:
        query = query.where(Editor.is_active == True)

    result = await db.execute(query)
    editors = result.scalars().all()

    responses = []
    for editor in editors:
        in_progress = await db.execute(
            select(func.count(ClientClip.id))
            .where(ClientClip.editor_id == editor.id)
            .where(ClientClip.status == ClipStatus.EDITING)
        )
        pending = await db.execute(
            select(func.count(ClientClip.id))
            .where(ClientClip.editor_id == editor.id)
            .where(ClientClip.status == ClipStatus.RAW)
        )
        responses.append(EditorResponse(
            **editor.__dict__,
            clips_in_progress=in_progress.scalar() or 0,
            clips_pending=pending.scalar() or 0,
        ))

    return responses


@router.get("/{editor_id}", response_model=EditorResponse)
async def get_editor(
    editor_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Editor)
        .where(Editor.id == editor_id)
        .where(Editor.user_id == current_user.id)
    )
    editor = result.scalar_one_or_none()
    if not editor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Editor not found")

    in_progress = await db.execute(
        select(func.count(ClientClip.id))
        .where(ClientClip.editor_id == editor.id)
        .where(ClientClip.status == ClipStatus.EDITING)
    )
    pending = await db.execute(
        select(func.count(ClientClip.id))
        .where(ClientClip.editor_id == editor.id)
        .where(ClientClip.status == ClipStatus.RAW)
    )
    return EditorResponse(
        **editor.__dict__,
        clips_in_progress=in_progress.scalar() or 0,
        clips_pending=pending.scalar() or 0,
    )


@router.patch("/{editor_id}", response_model=EditorResponse)
async def update_editor(
    editor_id: UUID,
    data: EditorUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Editor)
        .where(Editor.id == editor_id)
        .where(Editor.user_id == current_user.id)
    )
    editor = result.scalar_one_or_none()
    if not editor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Editor not found")

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(editor, key, value)

    await db.commit()
    await db.refresh(editor)
    logger.info(f"Updated editor {editor.name}")
    return EditorResponse(**editor.__dict__, clips_in_progress=0, clips_pending=0)


@router.delete("/{editor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_editor(
    editor_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Editor)
        .where(Editor.id == editor_id)
        .where(Editor.user_id == current_user.id)
    )
    editor = result.scalar_one_or_none()
    if not editor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Editor not found")

    editor.is_active = False
    await db.commit()
    logger.info(f"Deactivated editor {editor.name}")


@router.post("/{editor_id}/set-password", status_code=status.HTTP_204_NO_CONTENT)
async def set_editor_password(
    editor_id: UUID,
    data: EditorSetPassword,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Operator sets or resets an editor's portal login password."""
    result = await db.execute(
        select(Editor)
        .where(Editor.id == editor_id)
        .where(Editor.user_id == current_user.id)
    )
    editor = result.scalar_one_or_none()
    if not editor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Editor not found")

    editor.password_hash = hash_password(data.password)
    await db.commit()
    logger.info(f"Password updated for editor {editor.name}")

    # Optionally email the new credentials
    if editor.email:
        send_editor_welcome_email(
            editor_email=editor.email,
            editor_name=editor.name,
            password=data.password,
        )
