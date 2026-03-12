"""Client clip pipeline routes — RAW → EDITING → REVIEW → APPROVED → POSTED."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import Client, ClientClip, ClipStatus, Editor
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/client-clips", tags=["client-clips"])


class ClipCreate(BaseModel):
    client_id: UUID
    title: Optional[str] = None
    raw_file_path: Optional[str] = None
    hook_used: Optional[str] = None
    hashtags: Optional[str] = None


class ClipAssign(BaseModel):
    editor_id: UUID


class ClipStatusUpdate(BaseModel):
    status: ClipStatus


class ClipPerformanceUpdate(BaseModel):
    total_views: Optional[int] = None
    total_likes: Optional[int] = None
    total_comments: Optional[int] = None
    total_shares: Optional[int] = None
    tiktok_url: Optional[str] = None
    instagram_url: Optional[str] = None
    youtube_url: Optional[str] = None


class ClipResponse(BaseModel):
    id: UUID
    client_id: UUID
    editor_id: Optional[UUID]
    title: Optional[str]
    raw_file_path: Optional[str]
    edited_file_path: Optional[str]
    status: str

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else str(v)
    tiktok_url: Optional[str]
    instagram_url: Optional[str]
    youtube_url: Optional[str]
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    hook_used: Optional[str]
    hashtags: Optional[str]
    posted_at: Optional[datetime]
    created_at: datetime
    # computed
    client_name: Optional[str] = None
    editor_name: Optional[str] = None

    class Config:
        from_attributes = True


async def _verify_client_ownership(client_id: UUID, user_id: UUID, db: AsyncSession) -> Client:
    result = await db.execute(
        select(Client).where(Client.id == client_id).where(Client.user_id == user_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return client


@router.post("/", response_model=ClipResponse, status_code=status.HTTP_201_CREATED)
async def create_clip(
    data: ClipCreate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    client = await _verify_client_ownership(data.client_id, current_user.id, db)

    clip = ClientClip(
        client_id=data.client_id,
        title=data.title,
        raw_file_path=data.raw_file_path,
        hook_used=data.hook_used,
        hashtags=data.hashtags,
        status=ClipStatus.RAW,
    )
    db.add(clip)
    await db.commit()
    await db.refresh(clip)
    logger.info(f"Created clip for client {client.name}")
    return ClipResponse(**clip.__dict__, client_name=client.name)


@router.get("/", response_model=List[ClipResponse])
async def list_clips(
    client_id: Optional[UUID] = None,
    clip_status: Optional[ClipStatus] = None,
    editor_id: Optional[UUID] = None,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Join through Client to enforce ownership
    query = (
        select(ClientClip, Client)
        .join(Client, ClientClip.client_id == Client.id)
        .where(Client.user_id == current_user.id)
    )
    if client_id:
        query = query.where(ClientClip.client_id == client_id)
    if clip_status:
        query = query.where(ClientClip.status == clip_status)
    if editor_id:
        query = query.where(ClientClip.editor_id == editor_id)

    result = await db.execute(query)
    rows = result.all()

    responses = []
    for clip, client in rows:
        editor_name = None
        if clip.editor_id:
            ed = await db.execute(select(Editor).where(Editor.id == clip.editor_id))
            ed_obj = ed.scalar_one_or_none()
            editor_name = ed_obj.name if ed_obj else None
        responses.append(ClipResponse(
            **clip.__dict__,
            client_name=client.name,
            editor_name=editor_name,
        ))

    return responses


@router.get("/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientClip, Client)
        .join(Client, ClientClip.client_id == Client.id)
        .where(ClientClip.id == clip_id)
        .where(Client.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    clip, client = row
    return ClipResponse(**clip.__dict__, client_name=client.name)


@router.post("/{clip_id}/assign", response_model=ClipResponse)
async def assign_editor(
    clip_id: UUID,
    data: ClipAssign,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientClip, Client)
        .join(Client, ClientClip.client_id == Client.id)
        .where(ClientClip.id == clip_id)
        .where(Client.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    clip, client = row

    # Verify editor belongs to this operator
    ed_result = await db.execute(
        select(Editor).where(Editor.id == data.editor_id).where(Editor.user_id == current_user.id)
    )
    editor = ed_result.scalar_one_or_none()
    if not editor:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Editor not found")

    clip.editor_id = data.editor_id
    if clip.status == ClipStatus.RAW:
        clip.status = ClipStatus.EDITING

    await db.commit()
    await db.refresh(clip)
    logger.info(f"Assigned clip {clip_id} to editor {editor.name}")
    return ClipResponse(**clip.__dict__, client_name=client.name, editor_name=editor.name)


@router.patch("/{clip_id}/status", response_model=ClipResponse)
async def update_clip_status(
    clip_id: UUID,
    data: ClipStatusUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientClip, Client)
        .join(Client, ClientClip.client_id == Client.id)
        .where(ClientClip.id == clip_id)
        .where(Client.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    clip, client = row

    clip.status = data.status
    if data.status == ClipStatus.POSTED and not clip.posted_at:
        clip.posted_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(clip)
    logger.info(f"Clip {clip_id} status → {data.status.value}")
    return ClipResponse(**clip.__dict__, client_name=client.name)


@router.patch("/{clip_id}/performance", response_model=ClipResponse)
async def update_clip_performance(
    clip_id: UUID,
    data: ClipPerformanceUpdate,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ClientClip, Client)
        .join(Client, ClientClip.client_id == Client.id)
        .where(ClientClip.id == clip_id)
        .where(Client.user_id == current_user.id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clip not found")
    clip, client = row

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(clip, key, value)

    await db.commit()
    await db.refresh(clip)
    return ClipResponse(**clip.__dict__, client_name=client.name)
