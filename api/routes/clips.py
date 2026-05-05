"""
Clips API Routes — POST /api/clips/generate
Generate new clips for campaigns with quality control pipeline.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
import uuid

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from suno.common.models import User, Membership, Account, Campaign, Clip
from suno.common.enums import MembershipLifecycle, AccountStatus, ClipLifecycle
from suno.product.tier_helpers import can_create_clip
from suno.common.job_queue import JobQueueManager, JobQueueType
from suno.workers.clip_worker import generate_clip_job

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["clips"])


# Pydantic models
class GenerateClipRequest(BaseModel):
    campaign_id: UUID
    target_platforms: Optional[list[str]] = None
    tone: Optional[str] = None


class GenerateClipResponse(BaseModel):
    clip_id: int
    status: str
    job_id: str


@router.post("/clips/generate", response_model=GenerateClipResponse, status_code=201)
async def generate_clip(
    request: GenerateClipRequest,
    x_user_email: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate a new clip for a campaign.
    Returns 201 with clip_id, status, job_id.
    """
    # 1. Validate X-User-Email header
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    result = await db.execute(select(User).where(User.email == x_user_email))
    user = result.scalar_one_or_none()
    if not user:
        logger.warning(f"[CLIP_401] User not found: {x_user_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # 2. Check PENDING or ACTIVE membership
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status.in_(["pending", "active"]),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        logger.warning(f"[CLIP_403] No active membership: {x_user_email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # 3. Lazy daily reset
    if membership.updated_at.date() < datetime.utcnow().date() and membership.clips_today_count > 0:
        membership.clips_today_count = 0
        await db.commit()
        logger.info(f"[LAZY_RESET] Reset clips_today for membership {membership.id}")

    # 4. Check account status
    result = await db.execute(
        select(Account).where(Account.membership_id == membership.id)
    )
    account = result.scalar_one_or_none()

    if not account or account.status != AccountStatus.ACTIVE:
        logger.warning(f"[CLIP_403] Account not active: {x_user_email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not active"
        )

    # 5. Check can_create_clip
    can_create, reason = await can_create_clip(user.id, db)
    if not can_create:
        logger.warning(f"[CLIP_403] Cannot create clip: {reason}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason
        )

    # 6. Fetch campaign
    campaign_uuid = request.campaign_id

    result = await db.execute(
        select(Campaign).where(
            Campaign.id == campaign_uuid,
            Campaign.available == True
        )
    )
    campaign = result.scalar_one_or_none()

    if not campaign:
        logger.warning(f"[CLIP_404] Campaign not found: {request.campaign_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # 7. Duplicate check
    result = await db.execute(
        select(Clip).where(
            Clip.campaign_id == campaign_uuid,
            Clip.account_id == account.id,
            Clip.status.notin_(["failed", "rejected", "expired"])
        )
    )
    existing_clip = result.scalar_one_or_none()

    if existing_clip:
        logger.info(f"[CLIP_409] Duplicate in progress: campaign={request.campaign_id}, account={account.id}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Clip already in progress for this campaign"
        )

    # 8. Create clip
    clip = Clip(
        campaign_id=campaign_uuid,
        account_id=account.id,
        source_url=f"stub://{uuid.uuid4().hex}",
        source_platform="generated",
        title=f"Generated clip for {campaign.title}",
        description="",
        content_hash=uuid.uuid4().hex,
        status="queued",
        clip_metadata={
            "request_tone": request.tone,
            "request_platforms": request.target_platforms,
            "generated_at": datetime.utcnow().isoformat(),
        }
    )
    db.add(clip)
    await db.flush()
    clip_id = clip.id

    # 9. Enqueue generate_clip_job
    try:
        queue_manager = JobQueueManager()
        job_id = queue_manager.enqueue(
            JobQueueType.NORMAL,
            generate_clip_job,
            kwargs={
                "clip_id": clip_id,
                "account_id": account.id,
                "membership_id": membership.id,
            }
        )
        await db.commit()
        logger.info(f"[CLIP_ENQUEUED] clip_id={clip_id}, job_id={job_id}, account={account.id}")
    except Exception as e:
        await db.rollback()
        logger.error(f"[CLIP_ENQUEUE_FAILED] clip_id={clip_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue clip generation"
        )

    return GenerateClipResponse(
        clip_id=clip_id,
        status="needs_review".value,
        job_id=job_id
    )
