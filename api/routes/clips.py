"""
Clips API Routes — POST /api/clips/generate
Generate new clips for campaigns with quality control pipeline.
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
import uuid

from suno.database import SessionLocal
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


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/clips/generate", response_model=GenerateClipResponse, status_code=201)
def generate_clip(
    request: GenerateClipRequest,
    x_user_email: Optional[str] = Header(None),
    db: Session = Depends(get_db),
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

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        logger.warning(f"[CLIP_401] User not found: {x_user_email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # 2. Check PENDING or ACTIVE membership
    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        logger.warning(f"[CLIP_403] No active membership: {x_user_email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # 3. Lazy daily reset
    if membership.updated_at.date() < datetime.utcnow().date() and membership.clips_today_count > 0:
        membership.clips_today_count = 0
        db.commit()
        logger.info(f"[LAZY_RESET] Reset clips_today for membership {membership.id}")

    # 4. Check account status
    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if not account or account.status != AccountStatus.ACTIVE:
        logger.warning(f"[CLIP_403] Account not active: {x_user_email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account not active"
        )

    # 5. Check can_create_clip
    can_create, reason = can_create_clip(user.id, db)
    if not can_create:
        logger.warning(f"[CLIP_403] Cannot create clip: {reason}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason
        )

    # 6. Fetch campaign
    campaign_uuid = request.campaign_id

    campaign = db.query(Campaign).filter(
        Campaign.id == campaign_uuid,
        Campaign.available == True
    ).first()

    if not campaign:
        logger.warning(f"[CLIP_404] Campaign not found: {request.campaign_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )

    # 7. Duplicate check
    existing_clip = db.query(Clip).filter(
        Clip.campaign_id == campaign_uuid,
        Clip.account_id == account.id,
        Clip.status.notin_([ClipLifecycle.FAILED, ClipLifecycle.REJECTED, ClipLifecycle.EXPIRED])
    ).first()

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
        status=ClipLifecycle.QUEUED,
        clip_metadata={
            "request_tone": request.tone,
            "request_platforms": request.target_platforms,
            "generated_at": datetime.utcnow().isoformat(),
        }
    )
    db.add(clip)
    db.flush()
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
        db.commit()
        logger.info(f"[CLIP_ENQUEUED] clip_id={clip_id}, job_id={job_id}, account={account.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"[CLIP_ENQUEUE_FAILED] clip_id={clip_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to enqueue clip generation"
        )

    return GenerateClipResponse(
        clip_id=clip_id,
        status=ClipLifecycle.NEEDS_REVIEW.value,
        job_id=job_id
    )
