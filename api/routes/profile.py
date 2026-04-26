"""
User Profile Routes — Product Layer
GET /api/me, /api/me/membership, /api/me/workspace, /api/me/limits
"""

from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from suno.database import SessionLocal
from suno.common.models import User, Membership, Account, Tier
from suno.common.enums import AccountStatus, MembershipLifecycle, TierName

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


class DashboardDataResponse(BaseModel):
    user: MeResponse
    membership: MembershipResponse
    workspace: WorkspaceResponse
    limits: LimitsResponse


# Dependency: Get current user from header
def get_current_user_from_header(
    x_user_email: Optional[str] = None,
    db: Session = Depends(SessionLocal),
) -> User:
    """
    Get current user from X-User-Email header.
    Falls back to checking authorization headers.
    """
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    return user


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Endpoints
@router.get("/me", response_model=MeResponse)
def get_me(
    x_user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get current user info."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Get active or pending membership (allow both statuses for user access)
    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # Get account/workspace
    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    # Get tier
    tier = db.query(Tier).filter(Tier.id == membership.tier_id).first()

    return MeResponse(
        id=str(user.id),
        email=user.email,
        tier=tier.name.value if tier else "unknown",
        workspace_id=account.workspace_id,
        status=account.status.value,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


@router.get("/me/membership", response_model=MembershipResponse)
def get_me_membership(
    x_user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get current user's membership info."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # Get tier
    tier = db.query(Tier).filter(Tier.id == membership.tier_id).first()

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
def get_me_workspace(
    x_user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get current user's workspace/account info."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

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
def get_me_limits(
    x_user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get current user's tier limits and feature access."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    tier = db.query(Tier).filter(Tier.id == membership.tier_id).first()

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
def get_dashboard_data(
    x_user_email: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Get complete dashboard data in one request."""
    if not x_user_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-User-Email header"
        )

    user = db.query(User).filter(User.email == x_user_email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    tier = db.query(Tier).filter(Tier.id == membership.tier_id).first()

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
    )
