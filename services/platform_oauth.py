"""Platform OAuth handlers for TikTok and Instagram/Meta."""

import os
import logging
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlencode
import secrets

logger = logging.getLogger(__name__)


class TikTokOAuthService:
    """TikTok OAuth 2.0 handler using production credentials."""

    CLIENT_ID = os.getenv("TIKTOK_CLIENT_ID")
    CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
    AUTH_URL = "https://www.tiktok.com/v1/oauth/authorize"
    TOKEN_URL = "https://open-api.tiktok.com/v1/oauth/token"

    @staticmethod
    def get_authorization_url(redirect_uri: str) -> str:
        """Generate TikTok OAuth authorization URL."""
        if not TikTokOAuthService.CLIENT_ID:
            raise Exception("TIKTOK_CLIENT_ID not configured")

        params = {
            "client_key": TikTokOAuthService.CLIENT_ID,
            "scope": "user.info.basic,video.upload",
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": secrets.token_urlsafe(32),
        }
        auth_url = f"{TikTokOAuthService.AUTH_URL}?{urlencode(params)}"
        logger.info(f"TikTok OAuth URL: {auth_url[:100]}...")
        return auth_url

    @staticmethod
    async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict:
        """Exchange auth code for access token."""
        if not TikTokOAuthService.CLIENT_ID or not TikTokOAuthService.CLIENT_SECRET:
            raise Exception("TikTok OAuth credentials not configured")

        logger.info(f"TikTok: Exchanging code for token")

        payload = {
            "client_key": TikTokOAuthService.CLIENT_ID,
            "client_secret": TikTokOAuthService.CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    TikTokOAuthService.TOKEN_URL,
                    json=payload,
                )

                logger.info(f"TikTok token response status: {response.status_code}")

                # Read response content once (avoid double-read issues)
                response_text = response.text
                if response.status_code != 200:
                    logger.error(f"TikTok token exchange failed: {response_text}")
                    raise Exception(f"Token exchange failed: {response_text}")

                # Parse JSON from the already-read content
                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"TikTok response JSON parse failed: {response_text}")
                    raise Exception(f"Invalid JSON response: {response_text}")

                if data.get("error"):
                    error_msg = data.get("error_description", data.get("error"))
                    logger.error(f"TikTok OAuth error: {error_msg}")
                    raise Exception(f"OAuth error: {error_msg}")

                token_data = {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token"),
                    "expires_in": data.get("expires_in", 86400),
                    "open_id": data.get("open_id"),
                    "scope": data.get("scope", ""),
                }

                logger.info(f"TikTok token obtained. Expires in {token_data['expires_in']} seconds")
                return token_data

            except httpx.TimeoutException:
                logger.error("TikTok token request timeout")
                raise Exception("Request timeout")
            except Exception as e:
                logger.error(f"TikTok token exchange exception: {e}")
                raise

    @staticmethod
    async def refresh_token(refresh_token: str) -> Dict:
        """Refresh TikTok access token."""
        if not TikTokOAuthService.CLIENT_ID or not TikTokOAuthService.CLIENT_SECRET:
            raise Exception("TikTok OAuth credentials not configured")

        logger.info("TikTok: Refreshing access token")

        payload = {
            "client_key": TikTokOAuthService.CLIENT_ID,
            "client_secret": TikTokOAuthService.CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    TikTokOAuthService.TOKEN_URL,
                    json=payload,
                )

                # Read response content once (avoid double-read issues)
                response_text = response.text
                if response.status_code != 200:
                    logger.error(f"TikTok token refresh failed: {response_text}")
                    raise Exception("Token refresh failed")

                # Parse JSON from the already-read content
                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"TikTok refresh JSON parse failed: {response_text}")
                    raise Exception(f"Invalid JSON response: {response_text}")

                if data.get("error"):
                    error_msg = data.get("error_description", data.get("error"))
                    logger.error(f"TikTok refresh error: {error_msg}")
                    raise Exception(f"Refresh error: {error_msg}")

                return {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token"),
                    "expires_in": data.get("expires_in", 86400),
                }

            except Exception as e:
                logger.error(f"TikTok token refresh exception: {e}")
                raise


class InstagramOAuthService:
    """Instagram/Meta OAuth 2.0 handler."""

    APP_ID = os.getenv("META_APP_ID")
    APP_SECRET = os.getenv("META_APP_SECRET")
    AUTH_URL = "https://www.instagram.com/oauth/authorize"
    TOKEN_URL = "https://graph.instagram.com/v18.0/oauth/access_token"

    @staticmethod
    def get_authorization_url(redirect_uri: str) -> str:
        """Generate Instagram/Meta OAuth authorization URL."""
        if not InstagramOAuthService.APP_ID:
            raise Exception("META_APP_ID not configured")

        params = {
            "client_id": InstagramOAuthService.APP_ID,
            "redirect_uri": redirect_uri,
            "scope": "instagram_basic,instagram_content_publish",
            "response_type": "code",
            "state": secrets.token_urlsafe(32),
        }
        auth_url = f"{InstagramOAuthService.AUTH_URL}?{urlencode(params)}"
        logger.info(f"Instagram OAuth URL: {auth_url[:100]}...")
        return auth_url

    @staticmethod
    async def exchange_code_for_token(code: str, redirect_uri: str) -> Dict:
        """Exchange auth code for access token."""
        if not InstagramOAuthService.APP_ID or not InstagramOAuthService.APP_SECRET:
            raise Exception("Meta OAuth credentials not configured")

        logger.info("Instagram: Exchanging code for token")

        payload = {
            "client_id": InstagramOAuthService.APP_ID,
            "client_secret": InstagramOAuthService.APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code": code,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(
                    InstagramOAuthService.TOKEN_URL,
                    data=payload,
                )

                logger.info(f"Instagram token response status: {response.status_code}")

                # Read response content once (avoid double-read issues)
                response_text = response.text
                if response.status_code != 200:
                    logger.error(f"Instagram token exchange failed: {response_text}")
                    raise Exception(f"Token exchange failed: {response_text}")

                # Parse JSON from the already-read content
                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"Instagram response JSON parse failed: {response_text}")
                    raise Exception(f"Invalid JSON response: {response_text}")

                if data.get("error"):
                    error_msg = data.get("error", {}).get("message", "Unknown error")
                    logger.error(f"Instagram OAuth error: {error_msg}")
                    raise Exception(f"OAuth error: {error_msg}")

                access_token = data.get("access_token")
                user_id = data.get("user_id")

                # Get Instagram Business Account ID
                ig_account_id = await InstagramOAuthService.get_instagram_business_account(access_token)

                token_data = {
                    "access_token": access_token,
                    "user_id": user_id,
                    "instagram_business_account_id": ig_account_id,
                    "expires_in": data.get("expires_in", 5184000),  # 60 days
                }

                logger.info(f"Instagram token obtained. Expires in {token_data['expires_in']} seconds")
                return token_data

            except httpx.TimeoutException:
                logger.error("Instagram token request timeout")
                raise Exception("Request timeout")
            except Exception as e:
                logger.error(f"Instagram token exchange exception: {e}")
                raise

    @staticmethod
    async def get_instagram_business_account(access_token: str) -> Optional[str]:
        """Get Instagram Business Account ID from access token."""
        logger.info("Instagram: Fetching business account ID")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    "https://graph.instagram.com/v18.0/me/ig_business_account",
                    params={"access_token": access_token},
                )

                if response.status_code == 200:
                    data = response.json()
                    account_id = data.get("instagram_business_account_id")
                    logger.info(f"Instagram Business Account ID: {account_id}")
                    return account_id
                else:
                    logger.warning(
                        f"Could not fetch Instagram Business Account ID: {response.status_code}"
                    )
                    return None

            except Exception as e:
                logger.warning(f"Error fetching Instagram Business Account: {e}")
                return None

    @staticmethod
    async def refresh_token(access_token: str) -> Dict:
        """Refresh Instagram access token (long-lived)."""
        logger.info("Instagram: Refreshing access token")

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    "https://graph.instagram.com/v18.0/refresh_access_token",
                    params={
                        "grant_type": "ig_refresh_token",
                        "access_token": access_token,
                    },
                )

                # Read response content once (avoid double-read issues)
                response_text = response.text
                if response.status_code != 200:
                    logger.error(f"Instagram token refresh failed: {response_text}")
                    raise Exception("Token refresh failed")

                # Parse JSON from the already-read content
                try:
                    data = response.json()
                except Exception as json_err:
                    logger.error(f"Instagram refresh JSON parse failed: {response_text}")
                    raise Exception(f"Invalid JSON response: {response_text}")

                return {
                    "access_token": data.get("access_token"),
                    "expires_in": data.get("expires_in", 5184000),
                }

            except Exception as e:
                logger.error(f"Instagram token refresh exception: {e}")
                raise
