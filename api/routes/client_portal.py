"""Client-facing portal routes.

Authentication flow:
  1. Operator calls POST /api/portal/invite/{client_id} → gets magic link URL
  2. Operator emails/sends the link to their client
  3. Client visits /portal/access?token=<raw_token>
  4. Server validates token → sets client_access_token cookie (3 days)
  5. Client can now view /portal/dashboard, /portal/clips, /portal/invoices

All /api/portal/* data routes require the client_access_token cookie.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_client, get_current_user, get_db
from db.models_v2 import (
    Client,
    ClientClip,
    ClientPortalToken,
    ClipStatus,
    Invoice,
    PerformanceReport,
)
from services.auth import create_client_access_token
from services.email import send_portal_invite_email
from services.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/portal", tags=["client-portal"])

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TOKEN_EXPIRE_DAYS = 7


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Operator: generate invite link for a client
# ---------------------------------------------------------------------------

class InviteResponse(BaseModel):
    invite_url: str
    expires_at: datetime
    client_name: str


@router.post("/invite/{client_id}", response_model=InviteResponse)
async def create_portal_invite(
    client_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Operator generates a magic-link invite for a client.

    Returns a URL to send to the client. The token is valid for 7 days.
    Each call invalidates previous tokens for this client (by creating a new one;
    old tokens expire naturally).
    """
    # Verify the client belongs to this operator
    result = await db.execute(
        select(Client)
        .where(Client.id == client_id)
        .where(Client.user_id == current_user.id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)

    portal_token = ClientPortalToken(
        client_id=client_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(portal_token)
    await db.commit()

    invite_url = f"{BASE_URL}/portal/access?token={raw_token}"
    logger.info("Portal invite created for client %s by operator %s", client.name, current_user.email)

    # Auto-send invite email if client has an email on file
    if client.email:
        sent = send_portal_invite_email(
            client_email=client.email,
            client_name=client.name,
            invite_url=invite_url,
            expires_days=TOKEN_EXPIRE_DAYS,
            operator_name=None,  # Could be expanded to pass operator profile name
        )
        if sent:
            logger.info("Portal invite email sent to %s", client.email)
        else:
            logger.warning("Portal invite email failed for client %s (RESEND_API_KEY may not be set)", client.name)
    else:
        logger.warning("Client %s has no email — invite URL not emailed: %s", client.name, invite_url)

    return InviteResponse(
        invite_url=invite_url,
        expires_at=expires_at,
        client_name=client.name,
    )


# ---------------------------------------------------------------------------
# Client: exchange magic token for a session cookie
# ---------------------------------------------------------------------------

@router.get("/access")
async def portal_access(
    token: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Exchange a magic-link token for a client_access_token JWT cookie.

    Called automatically when the client visits /portal/access?token=...
    On success, sets the cookie and redirects to /portal/dashboard.
    """
    from fastapi.responses import RedirectResponse

    token_hash = _hash_token(token)
    result = await db.execute(
        select(ClientPortalToken).where(ClientPortalToken.token_hash == token_hash)
    )
    portal_token = result.scalar_one_or_none()

    if not portal_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired invite link")

    now = datetime.now(timezone.utc)
    if portal_token.expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invite link has expired")

    # Mark as used (but keep usable — same link works until expiry)
    portal_token.used_at = now
    await db.commit()

    client_jwt = create_client_access_token(str(portal_token.client_id))

    redirect = RedirectResponse(url="/portal/dashboard", status_code=302)
    redirect.set_cookie(
        key="client_access_token",
        value=client_jwt,
        httponly=True,
        secure=os.getenv("APP_ENV") == "production",
        samesite="lax",
        max_age=72 * 3600,  # 3 days
        path="/",
    )
    logger.info("Client portal access granted for client_id=%s", portal_token.client_id)
    return redirect


# ---------------------------------------------------------------------------
# Client portal API: data endpoints
# ---------------------------------------------------------------------------

class PortalClipResponse(BaseModel):
    id: UUID
    title: Optional[str]
    status: str
    tiktok_url: Optional[str]
    instagram_url: Optional[str]
    youtube_url: Optional[str]
    total_views: int
    total_likes: int
    hook_used: Optional[str]
    posted_at: Optional[datetime]
    created_at: datetime

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else str(v)

    model_config = ConfigDict(from_attributes=True)


class PortalInvoiceResponse(BaseModel):
    id: UUID
    month: str
    amount: float
    base_amount: float
    performance_bonus: float
    clips_delivered: int
    total_views: int
    view_guarantee_met: bool
    paid_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PortalReportResponse(BaseModel):
    id: UUID
    period_type: str
    period_start: datetime
    period_end: datetime
    total_clips: int
    total_views: int
    total_likes: int
    total_comments: int
    total_shares: int
    top_clips_json: Optional[list]
    best_hooks_json: Optional[list]
    insights_json: Optional[dict]
    created_at: datetime
    # computed
    avg_views_per_clip: int = 0
    period_label: str = ""

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_orm_with_computed(cls, report) -> "PortalReportResponse":
        avg = (report.total_views // report.total_clips) if report.total_clips else 0
        label = f"{report.period_start.strftime('%b %d')} → {report.period_end.strftime('%b %d, %Y')}"
        return cls.model_validate(
            {**{c.key: getattr(report, c.key) for c in report.__table__.columns}, "avg_views_per_clip": avg, "period_label": label}
        )


class PortalClientSummary(BaseModel):
    id: UUID
    name: str
    niche: Optional[str]
    monthly_rate: float
    clips_per_month: int
    view_guarantee: int
    tiktok_username: Optional[str]
    instagram_username: Optional[str]
    youtube_channel: Optional[str]
    status: str

    @field_validator("status", mode="before")
    @classmethod
    def coerce_status(cls, v):
        return v.value if hasattr(v, "value") else str(v)

    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=PortalClientSummary)
async def portal_me(
    current_client: Client = Depends(get_current_client),
):
    """Return the authenticated client's profile."""
    return PortalClientSummary.model_validate(current_client)


@router.get("/clips", response_model=List[PortalClipResponse])
async def portal_clips(
    clip_status: Optional[str] = None,
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    """List clips for this client — filtered by status if provided."""
    query = select(ClientClip).where(ClientClip.client_id == current_client.id)
    if clip_status:
        try:
            query = query.where(ClientClip.status == ClipStatus(clip_status.upper()))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {clip_status}")
    query = query.order_by(ClientClip.created_at.desc())

    result = await db.execute(query)
    clips = result.scalars().all()
    return [PortalClipResponse.model_validate(c) for c in clips]


@router.get("/invoices", response_model=List[PortalInvoiceResponse])
async def portal_invoices(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    """List all invoices for this client."""
    result = await db.execute(
        select(Invoice)
        .where(Invoice.client_id == current_client.id)
        .order_by(Invoice.month.desc())
    )
    invoices = result.scalars().all()
    return [PortalInvoiceResponse.model_validate(inv) for inv in invoices]


@router.get("/reports", response_model=List[PortalReportResponse])
async def portal_reports(
    current_client: Client = Depends(get_current_client),
    db: AsyncSession = Depends(get_db),
):
    """List performance reports for this client."""
    result = await db.execute(
        select(PerformanceReport)
        .where(PerformanceReport.client_id == current_client.id)
        .order_by(PerformanceReport.period_start.desc())
    )
    reports = result.scalars().all()
    return [PortalReportResponse.from_orm_with_computed(r) for r in reports]


@router.post("/logout")
async def portal_logout(response: Response):
    """Clear the client portal session cookie."""
    response.delete_cookie("client_access_token")
    return {"ok": True}
