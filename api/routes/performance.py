"""
Performance tracking endpoint: POST /api/clips/{clip_id}/performance
Phase 8: Manual performance recording.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from suno.database import SessionLocal
from suno.common.models import User, Membership, Account, Clip, ClipPerformance
from suno.common.enums import MembershipLifecycle
from suno.performance.learning_engine import PerformanceLearningEngine
from suno.common.job_queue import JobQueueManager, JobQueueType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["performance"])


class PerformanceDataIn(BaseModel):
    """Performance metrics submission."""
    platform: str = Field(..., min_length=1, max_length=50)
    variant_id: Optional[int] = None
    views: Optional[int] = Field(None, ge=0)
    watch_time_seconds: Optional[float] = Field(None, ge=0)
    completion_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    likes: Optional[int] = Field(None, ge=0)
    shares: Optional[int] = Field(None, ge=0)
    saves: Optional[int] = Field(None, ge=0)
    comments: Optional[int] = Field(None, ge=0)
    revenue_estimate: Optional[float] = Field(None, ge=0)


class PerformanceDataOut(BaseModel):
    """Performance metrics response."""
    performance_id: int
    clip_id: int
    platform: str
    views: int
    completion_rate: Optional[float]
    recorded_at: str

    class Config:
        from_attributes = True


@router.post(
    "/clips/{clip_id}/performance",
    response_model=PerformanceDataOut,
    status_code=status.HTTP_201_CREATED,
)
def record_clip_performance(
    clip_id: int,
    data: PerformanceDataIn,
    x_user_email: str = Header(..., alias="X-User-Email"),
):
    """
    Record performance metrics for a clip.
    Auth via X-User-Email header.
    """
    db = SessionLocal()
    try:
        # 1. Auth: Find user
        user = db.query(User).filter(User.email == x_user_email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Unauthorized")

        # 2. Membership: Check active membership
        membership = (
            db.query(Membership)
            .filter(Membership.user_id == user.id)
            .first()
        )
        if not membership or membership.status != MembershipLifecycle.ACTIVE:
            raise HTTPException(status_code=403, detail="No active membership")

        # 3. Account: Get account
        account = db.query(Account).filter(
            Account.membership_id == membership.id
        ).first()
        if not account:
            raise HTTPException(status_code=403, detail="Account not found")

        # 4. Clip: Verify belongs to account
        clip = db.query(Clip).filter(
            Clip.id == clip_id,
            Clip.account_id == account.id,
        ).first()
        if not clip:
            raise HTTPException(status_code=404, detail="Clip not found")

        # 5. Validation: completion_rate bounds
        if (data.completion_rate is not None and
            (data.completion_rate < 0.0 or data.completion_rate > 1.0)):
            raise HTTPException(
                status_code=422,
                detail="completion_rate must be between 0.0 and 1.0"
            )

        # 6. Record performance
        learning = PerformanceLearningEngine()
        perf_data = {
            "views": data.views or 0,
            "watch_time_seconds": data.watch_time_seconds,
            "completion_rate": data.completion_rate,
            "likes": data.likes or 0,
            "shares": data.shares or 0,
            "saves": data.saves or 0,
            "comments": data.comments or 0,
            "revenue_estimate": data.revenue_estimate,
        }

        perf = learning.record_performance(
            clip_id=clip_id,
            variant_id=data.variant_id,
            platform=data.platform,
            data=perf_data,
            db=db,
        )
        db.commit()

        # 7. Enqueue profile update job (async)
        queue = JobQueueManager()
        queue.enqueue(
            JobQueueType.LOW,
            "suno.workers.clip_worker.update_creator_profile_job",
            kwargs={"account_id": account.id},
        )

        logger.info(
            f"[PERFORMANCE_ENDPOINT] clip_id={clip_id}, account_id={account.id}, "
            f"platform={data.platform}, views={data.views or 0}"
        )

        return PerformanceDataOut(
            performance_id=perf.id,
            clip_id=perf.clip_id,
            platform=perf.platform,
            views=perf.views,
            completion_rate=perf.completion_rate,
            recorded_at=perf.recorded_at.isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[PERFORMANCE_FAILED] clip_id={clip_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    finally:
        db.close()
