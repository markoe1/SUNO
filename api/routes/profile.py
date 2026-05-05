"""
User Profile Routes — Product Layer
GET /api/me, /api/me/membership, /api/me/workspace, /api/me/limits
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from suno.common.models import User, Membership, Account, Tier, Clip
from suno.common.enums import AccountStatus, MembershipLifecycle, TierName, ClipLifecycle

router = APIRouter(prefix="/api", tags=["profile"])


# Pydantic models for responses
class MeResponse(BaseModel):
    id: str
    email: str
    tier: str
    workspace_id: str
    status: str
    created_at: str

    model_config = {"from_attributes": True}


class MembershipResponse(BaseModel):
    membership_id: int
    tier: str
    status: str
    whop_membership_id: str
    whop_plan_id: Optional[str]
    activated_at: Optional[str]
    clips_today_count: int

    model_config = {"from_attributes": True}


class WorkspaceResponse(BaseModel):
    workspace_id: str
    status: str
    automation_enabled: bool
    created_at: str

    model_config = {"from_attributes": True}


class LimitsResponse(BaseModel):
    tier: str
    max_daily_clips: int
    clips_used_today: int
    clips_remaining_today: int
    max_platforms: int
    features: Dict[str, bool]


class RecentClipResponse(BaseModel):
    clip_id: int
    status: str
    campaign_id: int
    overall_score: Optional[float]
    emotional_trigger_type: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


class ClipStatsResponse(BaseModel):
    clips_generated_today: int
    total_clips: int
    last_generated_at: Optional[str]
    needs_review_count: int
    approved_count: int
    recent_clips: List[RecentClipResponse]


class DashboardDataResponse(BaseModel):
    user: MeResponse
    membership: MembershipResponse
    workspace: WorkspaceResponse
    limits: LimitsResponse
    clip_stats: ClipStatsResponse


# Endpoints
@router.get("/me", response_model=MeResponse)
async def get_me(
    x_user_email: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current user info."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    result = await db.execute(select(User).where(User.email == x_user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Get active or pending membership (allow both statuses for user access)
    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status.in_(["pending", "active"]),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # Get account/workspace
    result = await db.execute(
        select(Account).where(Account.membership_id == membership.id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    # Get tier
    result = await db.execute(select(Tier).where(Tier.id == membership.tier_id))
    tier = result.scalar_one_or_none()

    return MeResponse(
        id=str(user.id),
        email=user.email,
        tier=tier.name.value if tier else "unknown",
        workspace_id=account.workspace_id,
        status=account.status.value,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.get("/me/membership", response_model=MembershipResponse)
async def get_me_membership(
    x_user_email: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's membership info."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    result = await db.execute(select(User).where(User.email == x_user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status.in_(["pending", "active"]),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # Get tier
    result = await db.execute(select(Tier).where(Tier.id == membership.tier_id))
    tier = result.scalar_one_or_none()

    return MembershipResponse(
        membership_id=membership.id,
        tier=tier.name.value if tier else "unknown",
        status=membership.status.value,
        whop_membership_id=membership.whop_membership_id,
        whop_plan_id=membership.whop_plan_id,
        activated_at=membership.activated_at.isoformat() if membership.activated_at else None,
        clips_today_count=membership.clips_today_count,
    )


@router.get("/me/workspace", response_model=WorkspaceResponse)
async def get_me_workspace(
    x_user_email: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's workspace/account info."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    result = await db.execute(select(User).where(User.email == x_user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status.in_(["pending", "active"]),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    result = await db.execute(
        select(Account).where(Account.membership_id == membership.id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    return WorkspaceResponse(
        workspace_id=account.workspace_id,
        status=account.status.value,
        automation_enabled=account.automation_enabled,
        created_at=account.created_at.isoformat() if account.created_at else "",
    )


@router.get("/me/limits", response_model=LimitsResponse)
async def get_me_limits(
    x_user_email: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get current user's tier limits and feature access."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    result = await db.execute(select(User).where(User.email == x_user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status.in_(["pending", "active"]),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    result = await db.execute(select(Tier).where(Tier.id == membership.tier_id))
    tier = result.scalar_one_or_none()

    if not tier:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tier configuration not found"
        )

    return LimitsResponse(
        tier=tier.name.value,
        max_daily_clips=tier.max_daily_clips,
        clips_used_today=membership.clips_today_count,
        clips_remaining_today=max(0, tier.max_daily_clips - membership.clips_today_count),
        max_platforms=tier.max_platforms,
        features={
            "scheduling": tier.scheduling,
            "analytics": tier.analytics,
            "api_access": tier.api_access,
            "auto_posting": tier.auto_posting,
        },
    )


@router.get("/dashboard/data", response_model=DashboardDataResponse)
async def get_dashboard_data(
    x_user_email: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Get complete dashboard data in one request."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    result = await db.execute(select(User).where(User.email == x_user_email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    result = await db.execute(
        select(Membership).where(
            Membership.user_id == user.id,
            Membership.status.in_(["pending", "active"]),
        )
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    result = await db.execute(
        select(Account).where(Account.membership_id == membership.id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    result = await db.execute(select(Tier).where(Tier.id == membership.tier_id))
    tier = result.scalar_one_or_none()

    # Get clip stats
    result = await db.execute(select(Clip).where(Clip.account_id == account.id))
    all_clips = result.scalars().all()
    total_clips = len(all_clips)
    clips_generated_today = membership.clips_today_count

    result = await db.execute(
        select(func.count(Clip.id)).where(
            Clip.account_id == account.id,
            Clip.status == "needs_review"
        )
    )
    needs_review_count = result.scalar() or 0

    result = await db.execute(
        select(func.count(Clip.id)).where(
            Clip.account_id == account.id,
            Clip.status == "approved"
        )
    )
    approved_count = result.scalar() or 0

    # Get recent clips (last 5)
    result = await db.execute(
        select(Clip).where(
            Clip.account_id == account.id
        ).order_by(Clip.created_at.desc()).limit(5)
    )
    recent_clips_data = result.scalars().all()

    recent_clips = [
        RecentClipResponse(
            clip_id=clip.id,
            status=clip.status.value,
            campaign_id=clip.campaign_id,
            overall_score=clip.overall_score,
            emotional_trigger_type=clip.emotional_trigger_type,
            created_at=clip.created_at.isoformat() if clip.created_at else "",
        )
        for clip in recent_clips_data
    ]

    last_generated_at = None
    if recent_clips_data:
        last_generated_at = recent_clips_data[0].created_at.isoformat() if recent_clips_data[0].created_at else None

    return DashboardDataResponse(
        user=MeResponse(
            id=str(user.id),
            email=user.email,
            tier=tier.name.value if tier else "unknown",
            workspace_id=account.workspace_id,
            status=account.status.value,
            created_at=user.created_at.isoformat() if user.created_at else "",
        ),
        membership=MembershipResponse(
            membership_id=membership.id,
            tier=tier.name.value if tier else "unknown",
            status=membership.status.value,
            whop_membership_id=membership.whop_membership_id,
            whop_plan_id=membership.whop_plan_id,
            activated_at=membership.activated_at.isoformat() if membership.activated_at else None,
            clips_today_count=membership.clips_today_count,
        ),
        workspace=WorkspaceResponse(
            workspace_id=account.workspace_id,
            status=account.status.value,
            automation_enabled=account.automation_enabled,
            created_at=account.created_at.isoformat() if account.created_at else "",
        ),
        limits=LimitsResponse(
            tier=tier.name.value if tier else "unknown",
            max_daily_clips=tier.max_daily_clips if tier else 0,
            clips_used_today=membership.clips_today_count,
            clips_remaining_today=max(0, (tier.max_daily_clips if tier else 0) - membership.clips_today_count),
            max_platforms=tier.max_platforms if tier else 0,
            features={
                "scheduling": tier.scheduling if tier else False,
                "analytics": tier.analytics if tier else False,
                "api_access": tier.api_access if tier else False,
                "auto_posting": tier.auto_posting if tier else False,
            },
        ),
        clip_stats=ClipStatsResponse(
            clips_generated_today=clips_generated_today,
            total_clips=total_clips,
            last_generated_at=last_generated_at,
            needs_review_count=needs_review_count,
            approved_count=approved_count,
            recent_clips=recent_clips,
        ),
    )
