"""Campaigns routes: list, sync trigger."""

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db
from db.models import Campaign, Job, User, UserSecret

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


class CampaignResponse(BaseModel):
    id: uuid.UUID
    whop_campaign_id: str
    name: str
    cpm: Optional[float] = None
    budget_remaining: Optional[float] = None
    is_free: bool
    drive_url: Optional[str] = None
    youtube_url: Optional[str] = None
    allowed_platforms: Optional[str] = None
    active: bool
    discovered_at: datetime
    last_checked: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=List[CampaignResponse])
async def list_campaigns(
    active_only: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    q = select(Campaign)
    if active_only:
        q = q.where(Campaign.active == True)
    q = q.order_by(Campaign.cpm.desc().nullslast())
    result = await db.execute(q)
    campaigns = result.scalars().all()
    return [CampaignResponse.model_validate(c) for c in campaigns]


@router.post("/sync")
async def trigger_sync(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enqueue a campaign sync job for the current user."""
    if current_user.jobs_paused:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Jobs are paused. Resume from Settings first.",
        )

    from workers.queue import q
    from workers.tasks.sync_campaigns import sync_campaigns

    job = Job(
        id=uuid.uuid4(),
        user_id=current_user.id,
        type="SYNC_CAMPAIGNS",
        status="pending",
        payload_json={},
    )
    db.add(job)
    await db.flush()

    rq_job = q.enqueue(
        sync_campaigns,
        kwargs={"user_id": str(current_user.id), "job_id": str(job.id)},
        job_id=str(uuid.uuid4()),
    )
    job.rq_job_id = rq_job.id
    await db.commit()

    return {"detail": "Campaign sync enqueued", "job_id": str(job.id)}
