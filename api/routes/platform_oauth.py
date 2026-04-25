"""Platform OAuth routes: TikTok, Instagram, Meta."""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from api.deps import get_db, get_current_user
from db.models import User
from services.platform_oauth import TikTokOAuthService, InstagramOAuthService

router = APIRouter(prefix="/api/oauth", tags=["oauth"])
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TIKTOK OAUTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/tiktok/start")
async def tiktok_oauth_start(
    user: User = Depends(get_current_user),
):
    """
    Initiate TikTok OAuth flow.
    Redirects user to TikTok authorization page.
    """
    redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/tiktok/callback"
    auth_url = TikTokOAuthService.get_authorization_url(redirect_uri)

    logger.info(f"TikTok OAuth: Initiating flow for user {user.id}")
    return RedirectResponse(url=auth_url)


@router.get("/tiktok/callback")
async def tiktok_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    TikTok OAuth callback handler.
    Exchanges auth code for access token and stores it.
    """
    if error:
        logger.warning(f"TikTok OAuth error: {error}")
        return RedirectResponse(
            url=f"/dashboard?error=tiktok_auth_failed&details={error}",
            status_code=status.HTTP_302_FOUND,
        )

    if not code:
        logger.warning("TikTok OAuth callback: No auth code received")
        return RedirectResponse(
            url="/dashboard?error=no_auth_code",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/tiktok/callback"

        # Exchange code for token
        token_data = await TikTokOAuthService.exchange_code_for_token(code, redirect_uri)

        logger.info(f"TikTok OAuth: Token obtained for open_id {token_data.get('open_id')}")

        # In production: Store to database here
        # For now: Store in session/database and redirect
        # cred = await PlatformCredential.store(...)

        # Redirect to dashboard with success
        return RedirectResponse(
            url="/dashboard?platform=tiktok&status=connected",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as e:
        logger.error(f"TikTok OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/dashboard?error=token_exchange_failed&details={str(e)}",
            status_code=status.HTTP_302_FOUND,
        )


# ─────────────────────────────────────────────────────────────────────────────
# INSTAGRAM/META OAUTH
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/instagram/start")
async def instagram_oauth_start(
    user: User = Depends(get_current_user),
):
    """
    Initiate Instagram/Meta OAuth flow.
    Redirects user to Meta authorization page.
    """
    if not os.getenv("META_APP_ID"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Instagram OAuth not configured. Contact admin.",
        )

    redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/instagram/callback"
    auth_url = InstagramOAuthService.get_authorization_url(redirect_uri)

    logger.info(f"Instagram OAuth: Initiating flow for user {user.id}")
    return RedirectResponse(url=auth_url)


@router.get("/instagram/callback")
async def instagram_oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Instagram/Meta OAuth callback handler.
    Exchanges auth code for access token and stores it.
    """
    if error:
        logger.warning(f"Instagram OAuth error: {error}")
        return RedirectResponse(
            url=f"/dashboard?error=instagram_auth_failed&details={error}",
            status_code=status.HTTP_302_FOUND,
        )

    if not code:
        logger.warning("Instagram OAuth callback: No auth code received")
        return RedirectResponse(
            url="/dashboard?error=no_auth_code",
            status_code=status.HTTP_302_FOUND,
        )

    try:
        redirect_uri = os.getenv("BASE_URL", "http://localhost:8000") + "/api/oauth/instagram/callback"

        # Exchange code for token
        token_data = await InstagramOAuthService.exchange_code_for_token(code, redirect_uri)

        logger.info(f"Instagram OAuth: Token obtained for user {token_data.get('user_id')}")

        # In production: Store to database here
        # cred = await PlatformCredential.store(...)

        # Redirect to dashboard with success
        return RedirectResponse(
            url="/dashboard?platform=instagram&status=connected",
            status_code=status.HTTP_302_FOUND,
        )

    except Exception as e:
        logger.error(f"Instagram OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/dashboard?error=token_exchange_failed&details={str(e)}",
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/health")
async def oauth_health():
    """Health check for OAuth endpoints."""
    return {
        "status": "ok",
        "tiktok": "configured" if os.getenv("TIKTOK_CLIENT_ID") else "not_configured",
        "instagram": "configured" if os.getenv("META_APP_ID") else "not_configured",
    }
