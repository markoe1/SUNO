"""Client management routes for operators."""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models_v2 import Client, ClientStatus, ClientClip, Invoice
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/clients", tags=["clients"])


# Request/Response models
class ClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = None
    niche: Optional[str] = None
    monthly_rate: float = Field(1500.0, ge=0)
    view_guarantee: int = Field(1000000, ge=0)
    clips_per_month: int = Field(60, ge=1)
    tiktok_username: Optional[str] = None
    instagram_username: Optional[str] = None
    youtube_channel: Optional[str] = None
    drive_folder: Optional[str] = None
    content_notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    email: Optional[str] = None
    niche: Optional[str] = None
    status: Optional[ClientStatus] = None
    monthly_rate: Optional[float] = Field(None, ge=0)
    view_guarantee: Optional[int] = Field(None, ge=0)
    clips_per_month: Optional[int] = Field(None, ge=1)
    tiktok_username: Optional[str] = None
    instagram_username: Optional[str] = None
    youtube_channel: Optional[str] = None
    drive_folder: Optional[str] = None
    content_notes: Optional[str] = None


class ClientResponse(BaseModel):
    id: UUID
    user_id: UUID
    name: str
    email: Optional[str]
    niche: Optional[str]
    status: str

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else str(v)
    monthly_rate: float
    view_guarantee: int
    clips_per_month: int
    tiktok_username: Optional[str]
    instagram_username: Optional[str]
    youtube_channel: Optional[str]
    drive_folder: Optional[str]
    content_notes: Optional[str]
    onboarded_at: Optional[datetime]
    churned_at: Optional[datetime]
    created_at: datetime
    
    # Computed fields
    total_clips: int = 0
    total_views: int = 0
    current_month_clips: int = 0
    current_month_views: int = 0
    total_revenue: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ClientListResponse(BaseModel):
    clients: List[ClientResponse]
    total: int
    active_count: int
    monthly_recurring_revenue: float


# CRUD Endpoints
@router.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(
    client_data: ClientCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new client for the operator."""
    
    # Create client
    client = Client(
        user_id=current_user.id,
        name=client_data.name,
        email=client_data.email,
        niche=client_data.niche,
        status=ClientStatus.LEAD,
        monthly_rate=client_data.monthly_rate,
        view_guarantee=client_data.view_guarantee,
        clips_per_month=client_data.clips_per_month,
        tiktok_username=client_data.tiktok_username,
        instagram_username=client_data.instagram_username,
        youtube_channel=client_data.youtube_channel,
        drive_folder=client_data.drive_folder,
        content_notes=client_data.content_notes,
    )
    
    db.add(client)
    await db.commit()
    await db.refresh(client)
    
    logger.info(f"Created client {client.name} for operator {current_user.email}")
    
    return ClientResponse(
        **client.__dict__,
        total_clips=0,
        total_views=0,
        current_month_clips=0,
        current_month_views=0,
        total_revenue=0.0
    )


@router.get("", response_model=ClientListResponse)
async def list_clients(
    status: Optional[ClientStatus] = None,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all clients for the operator."""
    
    # Build query
    query = select(Client).where(Client.user_id == current_user.id)
    
    if status:
        query = query.where(Client.status == status)
    
    result = await db.execute(query)
    clients = result.scalars().all()
    
    # Calculate metrics
    active_clients = [c for c in clients if c.status == ClientStatus.ACTIVE]
    monthly_recurring_revenue = sum(c.monthly_rate for c in active_clients)
    
    # Get additional metrics for each client
    client_responses = []
    for client in clients:
        # Get clip counts
        clip_count_result = await db.execute(
            select(func.count(ClientClip.id))
            .where(ClientClip.client_id == client.id)
        )
        total_clips = clip_count_result.scalar() or 0
        
        # Get total views
        views_result = await db.execute(
            select(func.sum(ClientClip.total_views))
            .where(ClientClip.client_id == client.id)
        )
        total_views = views_result.scalar() or 0
        
        # Get total revenue
        revenue_result = await db.execute(
            select(func.sum(Invoice.amount))
            .where(Invoice.client_id == client.id)
            .where(Invoice.paid_at.is_not(None))
        )
        total_revenue = revenue_result.scalar() or 0.0
        
        client_responses.append(ClientResponse(
            **client.__dict__,
            total_clips=total_clips,
            total_views=total_views,
            current_month_clips=0,  # TODO: Calculate
            current_month_views=0,  # TODO: Calculate
            total_revenue=total_revenue
        ))
    
    return ClientListResponse(
        clients=client_responses,
        total=len(clients),
        active_count=len(active_clients),
        monthly_recurring_revenue=monthly_recurring_revenue
    )


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific client."""
    
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id)
        .where(Client.user_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Get metrics
    clip_count_result = await db.execute(
        select(func.count(ClientClip.id))
        .where(ClientClip.client_id == client.id)
    )
    total_clips = clip_count_result.scalar() or 0
    
    views_result = await db.execute(
        select(func.sum(ClientClip.total_views))
        .where(ClientClip.client_id == client.id)
    )
    total_views = views_result.scalar() or 0
    
    revenue_result = await db.execute(
        select(func.sum(Invoice.amount))
        .where(Invoice.client_id == client.id)
        .where(Invoice.paid_at.is_not(None))
    )
    total_revenue = revenue_result.scalar() or 0.0
    
    return ClientResponse(
        **client.__dict__,
        total_clips=total_clips,
        total_views=total_views,
        current_month_clips=0,  # TODO: Calculate
        current_month_views=0,  # TODO: Calculate
        total_revenue=total_revenue
    )


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    client_data: ClientUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update a client."""
    
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id)
        .where(Client.user_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Update fields
    update_data = client_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    
    # Handle status changes
    if client_data.status == ClientStatus.ACTIVE and not client.onboarded_at:
        client.onboarded_at = datetime.now(timezone.utc)
    elif client_data.status == ClientStatus.CHURNED and not client.churned_at:
        client.churned_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(client)
    
    logger.info(f"Updated client {client.name}")
    
    return ClientResponse(
        **client.__dict__,
        total_clips=0,
        total_views=0,
        current_month_clips=0,
        current_month_views=0,
        total_revenue=0.0
    )


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(
    client_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a client (soft delete by setting status to CHURNED)."""
    
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id)
        .where(Client.user_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    # Soft delete
    client.status = ClientStatus.CHURNED
    client.churned_at = datetime.now(timezone.utc)
    
    await db.commit()
    
    logger.info(f"Soft deleted client {client.name}")


@router.post("/{client_id}/activate", response_model=ClientResponse)
async def activate_client(
    client_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Activate a client (move from LEAD/TRIAL to ACTIVE)."""
    
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id)
        .where(Client.user_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found"
        )
    
    if client.status == ClientStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client is already active"
        )
    
    client.status = ClientStatus.ACTIVE
    client.onboarded_at = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(client)
    
    logger.info(f"Activated client {client.name}")
    
    return ClientResponse(
        **client.__dict__,
        total_clips=0,
        total_views=0,
        current_month_clips=0,
        current_month_views=0,
        total_revenue=0.0
    )