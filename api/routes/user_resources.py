"""
User Resource Write Operations — Product Layer
POST /api/campaigns, PATCH /api/me/workspace
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from suno.database import SessionLocal
from suno.common.models import User, Membership, Account, Campaign
from suno.common.enums import MembershipLifecycle
from suno.product.tier_helpers import can_create_clip

router = APIRouter(prefix="/api", tags=["user_resources"])


# Pydantic models for requests
class CampaignCreate(BaseModel):
    source_url: str
    source_type: str
    title: str
    keywords: Optional[List[str]] = None
    target_platforms: Optional[List[str]] = None
    tone: Optional[str] = None
    style: Optional[str] = None
    duration_seconds: Optional[int] = 30


class WorkspaceUpdate(BaseModel):
    automation_enabled: Optional[bool] = None


# Pydantic models for responses
class CampaignResponse(BaseModel):
    id: int
    source_id: str
    source_type: str
    title: str
    keywords: List[str]
    target_platforms: List[str]
    tone: Optional[str]
    style: Optional[str]
    duration_seconds: int
    available: bool

    model_config = {"from_attributes": True}


class WorkspaceResponse(BaseModel):
    workspace_id: str
    status: str
    automation_enabled: bool
    created_at: str

    model_config = {"from_attributes": True}


# Dependency: Get database session
def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Endpoints
@router.post("/campaigns", response_model=CampaignResponse, status_code=201)
def create_campaign(
    campaign_data: CampaignCreate,
    x_user_email: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Register a TikTok/YouTube/etc. URL as a clip source."""
    # 1. Validate X-User-Email header → find User
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

    # 2. Check PENDING or ACTIVE membership → 403 if none
    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # 3. Check account exists → 403 if none
    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    # 4. Check can_create_clip feature gate (tier limits)
    can_create, reason = can_create_clip(user.id, db)
    if not can_create:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Cannot create clip: {reason}"
        )

    # 5. Deduplicate: check (source_url, source_type) unique constraint
    existing = db.query(Campaign).filter(
        Campaign.source_id == campaign_data.source_url,
        Campaign.source_type == campaign_data.source_type,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign source already registered"
        )

    # 6. Create Campaign(source_id=source_url, source_type=source_type, ...)
    new_campaign = Campaign(
        source_id=campaign_data.source_url,
        source_type=campaign_data.source_type,
        title=campaign_data.title,
        keywords=campaign_data.keywords or [],
        target_platforms=campaign_data.target_platforms or [],
        tone=campaign_data.tone,
        style=campaign_data.style,
        duration_seconds=campaign_data.duration_seconds or 30,
        available=True,
    )

    try:
        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign source already registered"
        )

    # 7. Return CampaignResponse (201)
    return CampaignResponse(
        id=new_campaign.id,
        source_id=new_campaign.source_id,
        source_type=new_campaign.source_type,
        title=new_campaign.title,
        keywords=new_campaign.keywords,
        target_platforms=new_campaign.target_platforms,
        tone=new_campaign.tone,
        style=new_campaign.style,
        duration_seconds=new_campaign.duration_seconds,
        available=new_campaign.available,
    )


@router.patch("/me/workspace", response_model=WorkspaceResponse, status_code=200)
def update_workspace(
    workspace_data: WorkspaceUpdate,
    x_user_email: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Update workspace settings (automation_enabled)."""
    # 1. Validate X-User-Email header → find User
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

    # 2. Check PENDING or ACTIVE membership → 403 if none
    membership = db.query(Membership).filter(
        Membership.user_id == user.id,
        Membership.status.in_([MembershipLifecycle.PENDING, MembershipLifecycle.ACTIVE]),
    ).first()

    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active membership"
        )

    # 3. Find Account via membership_id → 403 if none
    account = db.query(Account).filter(
        Account.membership_id == membership.id
    ).first()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No account provisioned"
        )

    # 4. Apply only fields that were set (model_dump(exclude_unset=True))
    update_data = workspace_data.model_dump(exclude_unset=True)

    # 5. setattr loop to update Account fields
    for field, value in update_data.items():
        setattr(account, field, value)

    db.commit()
    db.refresh(account)

    # 6. Return updated WorkspaceResponse
    return WorkspaceResponse(
        workspace_id=account.workspace_id,
        status=account.status.value,
        automation_enabled=account.automation_enabled,
        created_at=account.created_at.isoformat() if account.created_at else "",
    )
